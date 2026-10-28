from strattester.engine.data_first import DataFirstScheduler
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.persistence.data_first_store import DataFirstStateStore
from strattester.strategies.base import DataRequirement,StrategyDefinition
from strattester.strategies.registry import StrategyRegistry

class Count:
    seen=[]
    def run_context(self,context,checkpoint=None):
        self.seen.append(context.symbol)
        return len(list(context.candles()))

class NoRequests:
    def fetch_klines(self,*args,**kwargs):
        raise AssertionError('preloaded fixture must not download')

def fixture(tmp_path,category='linear',path=None):
    Count.seen=[]
    state=DataFirstStateStore(tmp_path/'state.db')
    registry=StrategyRegistry()
    registry.register(StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count))
    path=path or tmp_path/'market.db'
    def stores(category):return SQLiteMarketStore.open(path)
    scheduler=DataFirstScheduler(state,registry,lambda c:NoRequests(),stores,categories=(category,),clock_ms=lambda:600000)
    state.snapshot(category,[{'symbol':'SAME','status':'Trading','launchTime':'0'}],1)
    store=stores(category)
    store.bind_market_category(category)
    store.upsert_candles([Candle('SAME','1m',0,100,101,99,100,1)])
    store.close()
    return scheduler,state,registry,stores

def test_disable_during_final_admission_prevents_execution(tmp_path):
    scheduler,state,registry,_=fixture(tmp_path)
    scheduler.plan(start_ms=0,end_ms=60000)
    calls=[0]
    def admission():
        calls[0]+=1
        if calls[0]==2:registry.set_enabled('count','1',False)
        return True
    scheduler.resource_admission=admission
    scheduler.tick()
    assert Count.seen==[], state.jobs()[0]
    assert state.jobs()[0]['result'] is None

def test_changed_history_provenance_invalidates_planned_archive(tmp_path):
    scheduler,state,registry,_=fixture(tmp_path)
    row={'symbol':'SAME','status':'Closed','launchTime':'0','deliveryTime':'120000'}
    state.register_history('linear',row,[(0,60000)],source_sha256='a'*64,observed_at=2)
    scheduler.plan(start_ms=0,end_ms=120000)
    state.register_history('linear',row,[(60000,120000)],source_sha256='b'*64,observed_at=3)
    scheduler.tick()
    assert Count.seen==[], state.jobs()[0]
    assert state.jobs()[0]['result'] is None

def test_category_alias_rejected_across_scheduler_instances(tmp_path):
    scheduler,state,registry,stores=fixture(tmp_path)
    scheduler.plan(start_ms=0,end_ms=60000)
    scheduler.tick()
    assert state.jobs()[0]['state']=='COMPLETED'
    Count.seen=[]
    state.snapshot('spot',[{'symbol':'SAME','status':'Trading','launchTime':'0'}],2)
    other=DataFirstScheduler(state,registry,lambda c:NoRequests(),stores,categories=('spot',),clock_ms=lambda:600000)
    other.plan(start_ms=0,end_ms=60000)
    other.tick()
    job=next(j for j in state.jobs() if j['payload']['instrument']['category']=='spot')
    assert job['state']!='COMPLETED', job
    assert Count.seen==[]

def test_conflicting_duplicate_source_timestamp_never_completes(tmp_path):
    scheduler,state,registry,stores=fixture(tmp_path)
    store=stores('linear')
    store.connection.execute('DELETE FROM candles')
    store.connection.commit()
    store.close()
    class ConflictingPage:
        def fetch_klines(self,*args,**kwargs):
            return [['0','100','101','99','100','1','100'],
                    ['0','100','101','99','101','1','100']]
    scheduler.client_factory=lambda c:ConflictingPage()
    scheduler.plan(start_ms=0,end_ms=60000)
    scheduler.tick()
    assert state.jobs()[0]['state']!='COMPLETED',state.jobs()[0]
    assert Count.seen==[]


def test_expired_lease_cannot_publish_completed_result(tmp_path):
    import pytest
    scheduler,state,_,_=fixture(tmp_path)
    key=scheduler.plan(start_ms=0,end_ms=60000)[0]
    token=state.claim(key,'worker',0,100,max_active=1)
    state.transition(key,'worker',token,0,'RUNNING')
    with pytest.raises(RuntimeError,match='fenced'):
        state.transition(key,'worker',token,101,'COMPLETED',result={'x':1},release=True)
    assert state.get(key)['result'] is None
    assert state.claim(key,'other',101,100,max_active=1) is None
    assert state.get(key)['state']=='BLOCKED'

def test_global_claim_limit_and_partition_exclusion(tmp_path):
    scheduler,state,_,_=fixture(tmp_path)
    first=scheduler.plan(start_ms=0,end_ms=60000)[0]
    second=scheduler.plan(start_ms=0,end_ms=120000)[0]
    state.snapshot('spot',[{'symbol':'OTHER','status':'Trading','launchTime':'0'}],2)
    other=DataFirstScheduler(state,scheduler.registry,scheduler.client_factory,scheduler.store_factory,categories=('spot',),clock_ms=lambda:600000)
    third=other.plan(start_ms=0,end_ms=60000)[0]
    assert state.claim(first,'one',0,100,max_active=2)
    assert state.claim(second,'two',0,100,max_active=2) is None
    assert state.claim(third,'two',0,100,max_active=1) is None
    assert state.claim(third,'two',0,100,max_active=2)

def test_research_snapshot_keeps_original_values_across_concurrent_writer(tmp_path):
    scheduler,state,_,stores=fixture(tmp_path)
    reader=stores('linear')
    writer=stores('linear')
    try:
        with reader.research_snapshot('SAME') as snap:
            before=list(snap.iter_candles('SAME'))
            writer.upsert_candles([Candle('SAME','1m',0,100,101,99,101,1)])
            assert list(snap.iter_candles('SAME'))==before
        assert list(reader.iter_candles('SAME'))[0].close==101
    finally:
        writer.close()
        reader.close()

def test_interrupted_running_strategy_is_not_automatically_replayed(tmp_path):
    scheduler,state,_,_=fixture(tmp_path)
    flag=[False]
    calls=[]
    class InterruptedStrategy:
        def run_context(self,context,checkpoint=None):
            calls.append(checkpoint)
            if len(calls)==1:flag[0]=True
            return len(list(context.candles()))
    registry=StrategyRegistry()
    registry.register(StrategyDefinition('interrupted','1',(DataRequirement('candles',('1m',)),),InterruptedStrategy))
    scheduler.registry=registry
    scheduler.external_cancel=lambda:flag[0]
    key=scheduler.plan(start_ms=0,end_ms=60000)[0]
    scheduler.tick()
    assert calls==[None]
    assert state.get(key)['result'] is None
    flag[0]=False
    scheduler.tick()
    assert calls==[None],state.get(key)
    assert state.get(key)['state']=='BLOCKED'

def test_persisted_ready_is_revalidated_after_market_rows_disappear(tmp_path):
    scheduler,state,_,stores=fixture(tmp_path)
    key=scheduler.plan(start_ms=0,end_ms=60000)[0]
    admission_calls=[0]
    def admission():
        admission_calls[0]+=1
        return admission_calls[0]==1
    scheduler.resource_admission=admission
    scheduler.tick()
    assert state.get(key)['state']=='READY' and Count.seen==[]
    store=stores('linear')
    store.connection.execute('DELETE FROM candles')
    store.connection.commit()
    store.close()
    scheduler.resource_admission=lambda:True
    scheduler.tick()
    assert state.get(key)['state']!='COMPLETED'
    assert state.get(key)['result'] is None and Count.seen==[]
