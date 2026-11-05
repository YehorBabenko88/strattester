import json
import socket
import threading
from pathlib import Path
import pytest
from strattester.engine.data_first import DataFirstScheduler
from strattester.marketdata.bybit_client import BybitClient,RetryPolicy
from strattester.marketdata.history_planner import HistoryPlanner
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.persistence.data_first_store import DataFirstStateStore
from strattester.strategies.base import DataRequirement,StrategyDefinition
from strattester.strategies.registry import StrategyRegistry

class Count:
    seen=[]
    lock=threading.Lock()
    def run_context(self,context,checkpoint=None):
        rows=list(context.candles())
        with self.lock:self.seen.append(context.symbol)
        return {'count':len(rows),'symbol':context.symbol}

class Response:
    status_code=200;headers={}
    def __init__(self,data):self.data=data
    def json(self):return self.data

class Transport:
    def __init__(self,rows,calls,*,empty=(),page_rows=1):
        self.rows=rows;self.calls=calls;self.empty=empty;self.page_rows=page_rows
    def close(self):pass
    def get(self,url,params,timeout,**kwargs):
        self.calls.append((url,dict(params)))
        if url.endswith('instruments-info'):
            rows=self.rows[params['category']];offset=int(params.get('cursor','0'))
            chunk=rows[offset:offset+1]
            next_cursor=str(offset+1) if offset+1<len(rows) else ''
            return Response({'retCode':0,'result':{'category':params['category'],'list':chunk,'nextPageCursor':next_cursor}})
        assert url.endswith('kline')
        if params['symbol'] in self.empty:data=[]
        else:
            step=int(params['interval'])*60000
            times=list(range(((params['start']+step-1)//step)*step,params['end']+1,step))
            data=[[str(t),'100','101','99','100','1','100'] for t in reversed(times[-self.page_rows:])]
        return Response({'retCode':0,'result':{'list':data}})

@pytest.fixture(autouse=True)
def no_actual_network(monkeypatch):
    def deny(*a,**k):raise AssertionError('real network forbidden in source tests')
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket,'getaddrinfo',deny)

def setup(tmp_path,*,rows=None,empty=(),minimum=1,requirements=None,max_jobs=16,cancel=lambda:False):
    rows=rows or {'linear':[{'symbol':'ALPHAUSDT','status':'Trading','launchTime':'0'}]}
    calls=[];registry=StrategyRegistry();Count.seen=[]
    registry.register(StrategyDefinition('count','1',requirements or (DataRequirement('candles',('1m',),min_observations=minimum),),Count))
    state=DataFirstStateStore(tmp_path/'coordinator.db')
    def clients(category):return BybitClient(session=Transport(rows,calls,empty=empty),retry=RetryPolicy(1,0,0))
    def stores(category):
        store=SQLiteMarketStore.open(tmp_path/(category+'.db'))
        store.bind_market_category(category)
        return store
    scheduler=DataFirstScheduler(state,registry,clients,stores,categories=tuple(rows),requests_per_second=20,
        clock_ms=lambda:600000,max_jobs_per_tick=max_jobs,max_pages_per_job=1,cancel=cancel)
    return scheduler,state,calls,registry,stores

def test_end_to_end_dynamic_universe_restart_and_no_redownload(tmp_path):
    scheduler,state,calls,registry,stores=setup(tmp_path)
    scheduler.discover();keys=scheduler.plan(start_ms=0,end_ms=180000)
    for _ in range(4):scheduler.tick()
    job=state.get(keys[0]);assert job['state']=='COMPLETED',job
    assert job['result']['output']=={'count':3,'symbol':'ALPHAUSDT'}
    assert [p['end'] for u,p in calls if u.endswith('kline')]==[120000,60000,0]
    events=[e['state'] for e in state.events(keys[0])]
    assert all(s in events for s in ('DISCOVERED','SYNCING','PARTIAL','READY','RUNNING','COMPLETED'))
    before=len(calls)
    restarted=DataFirstScheduler(state,registry,scheduler.client_factory,stores,clock_ms=lambda:600000,requests_per_second=20)
    assert restarted.plan(start_ms=0,end_ms=180000)==keys
    restarted.tick();assert len(calls)==before and Count.seen==['ALPHAUSDT']

def test_ready_instrument_runs_while_other_is_partial(tmp_path):
    rows={'linear':[{'symbol':s,'status':'Trading','launchTime':'0'} for s in ('READYUSDT','SLOWUSDC')]}
    scheduler,state,calls,_,stores=setup(tmp_path,rows=rows,empty={'SLOWUSDC'})
    store=stores('linear');store.upsert_candles([Candle('READYUSDT','1m',t,100,101,99,100,1) for t in (0,60000,120000)]);store.close()
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    jobs={j['payload']['instrument']['symbol']:j for j in state.jobs()}
    assert jobs['READYUSDT']['state']=='COMPLETED'
    assert jobs['SLOWUSDC']['state']=='PARTIAL'
    assert Count.seen==['READYUSDT']
    assert not any(p.get('symbol')=='READYUSDT' for u,p in calls if u.endswith('kline'))

def test_missing_event_history_never_runs_or_uses_recent_trades(tmp_path):
    req=(DataRequirement('candles',('1m',)),DataRequirement('funding',('480m',)),
         DataRequirement('public_trades'),DataRequirement('orderbook_l2'))
    scheduler,state,calls,_,_=setup(tmp_path,requirements=req)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    assert state.jobs()[0]['state']=='BLOCKED'
    assert 'HISTORICAL_CONTRACT_REQUIRED' in state.jobs()[0]['reason']
    assert not Count.seen and all('instruments-info' in u for u,p in calls)

def test_new_listing_minimum_blocks_without_fetch(tmp_path):
    rows={'linear':[{'symbol':'NEWUSDC','status':'Trading','launchTime':'120001'}]}
    scheduler,state,calls,_,_=setup(tmp_path,rows=rows,minimum=2)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    assert state.jobs()[0]['state']=='BLOCKED' and not Count.seen
    assert not any(u.endswith('kline') for u,p in calls)

def test_delisted_history_uses_only_explicit_activity_intervals(tmp_path):
    scheduler,state,calls,_,_=setup(tmp_path)
    state.register_history('linear',{'symbol':'DEADUSDT','status':'Closed','launchTime':'0','deliveryTime':'300000'},
                           [(0,120000),(180000,300000)],source_sha256='a'*64,observed_at=600000)
    scheduler.plan(start_ms=0,end_ms=600000)
    for _ in range(4):scheduler.tick()
    assert len(state.jobs())==2 and all(j['state']=='COMPLETED' for j in state.jobs())
    assert sorted(j['result']['output']['count'] for j in state.jobs())==[2,2]
    assert not any(p.get('start',0)<=120000<=p.get('end',-1) for u,p in calls if u.endswith('kline'))

def test_unknown_launch_and_unobserved_delist_are_not_invented(tmp_path):
    scheduler,state,_,_,_=setup(tmp_path)
    state.snapshot('linear',[{'symbol':'UNKNOWN','status':'Trading'}],1)
    scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    assert state.jobs()[0]['state']=='BLOCKED' and 'UNKNOWN_LAUNCH' in state.jobs()[0]['reason']
    state.snapshot('linear',[],2)
    metadata=state.instruments()[0]['metadata']
    assert metadata['status']=='MISSING' and metadata['deliveryTime'] is None

def test_disabled_after_plan_cannot_bypass_executor(tmp_path):
    scheduler,state,_,registry,_=setup(tmp_path)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000)
    registry.set_enabled('count','1',False);scheduler.tick()
    assert not Count.seen and state.jobs()[0]['state']=='FAILED'

def test_cancel_checkpoint_restart_only_missing_page(tmp_path):
    flag=[False];scheduler,state,calls,_,_=setup(tmp_path,cancel=lambda:flag[0])
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    assert state.jobs()[0]['progress']['last_page']['page_end']==120000
    flag[0]=True;scheduler.tick();assert len([u for u,p in calls if u.endswith('kline')])==1
    flag[0]=False
    scheduler.tick();scheduler.tick()
    assert state.jobs()[0]['state']=='COMPLETED'
    assert [p['end'] for u,p in calls if u.endswith('kline')]==[120000,60000,0]

def test_expired_running_lease_is_not_automatically_replayed(tmp_path):
    scheduler,state,_,_,_=setup(tmp_path)
    scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=60000)[0]
    token=state.claim(key,'old',0,10)
    state.transition(key,'old',token,0,'RUNNING')
    assert state.claim(key,'new',11,10) is None
    assert state.get(key)['state']=='BLOCKED' and not Count.seen

def test_market_categories_never_share_symbol_storage(tmp_path):
    rows={c:[{'symbol':'SAME','status':'Trading','launchTime':'0'}] for c in ('linear','spot')}
    scheduler,state,calls,_,_=setup(tmp_path,rows=rows)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000);scheduler.tick()
    assert all(j['state']=='COMPLETED' for j in state.jobs())
    assert {p['category'] for u,p in calls if u.endswith('kline')}=={'linear','spot'}

def test_fair_queue_does_not_starve_unselected_instrument(tmp_path):
    rows={'linear':[{'symbol':s,'status':'Trading','launchTime':'0'} for s in ('A','B','C')]}
    scheduler,state,_,_,_=setup(tmp_path,rows=rows,empty={'A','B','C'},max_jobs=1)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000)
    for _ in range(3):scheduler.tick()
    assert all(j['state']=='PARTIAL' for j in state.jobs())

def test_strategy_cannot_write_research_snapshot(tmp_path):
    scheduler,state,_,registry,_=setup(tmp_path)
    class Writes:
        def run_context(self,context,checkpoint=None):
            context.store.connection.execute('DELETE FROM candles')
    registry.register(StrategyDefinition('writes','1',(DataRequirement('candles',('1m',)),),Writes))
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000)
    for _ in range(3):scheduler.tick()
    jobs={j['payload']['strategy_id']:j for j in state.jobs()}
    assert jobs['count']['state']=='COMPLETED'
    assert jobs['writes']['state']=='FAILED' and jobs['writes']['result'] is None

def test_ready_result_publishes_before_other_network_page_finishes(tmp_path,monkeypatch):
    rows={'linear':[{'symbol':s,'status':'Trading','launchTime':'0'} for s in ('READY','SLOW')]}
    scheduler,state,_,_,stores=setup(tmp_path,rows=rows)
    store=stores('linear');store.upsert_candles([Candle('READY','1m',0,100,101,99,100,1)]);store.close()
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000)
    entered=threading.Event();release=threading.Event();original=Transport.get
    def delayed(self,url,params,timeout,**kw):
        if url.endswith('kline') and params['symbol']=='SLOW':
            entered.set();assert release.wait(5)
        return original(self,url,params,timeout,**kw)
    monkeypatch.setattr(Transport,'get',delayed)
    worker=threading.Thread(target=scheduler.tick)
    worker.start()
    try:
        assert entered.wait(3)
        import time
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            ready=next(j for j in state.jobs() if j['payload']['instrument']['symbol']=='READY')
            if ready['state']=='COMPLETED':break
            time.sleep(.01)
        assert ready['state']=='COMPLETED' and not release.is_set()
    finally:release.set();worker.join(5)
    assert not worker.is_alive()

def test_canonical_sharded_store_reaches_backtest_result(tmp_path):
    from strattester.marketdata.store_factory import open_market_store
    from strattester.strategies.builtin.legacy_grid import LegacyGridStrategy
    scheduler,state,_,registry,_=setup(tmp_path)
    registry.register(StrategyDefinition('legacy_grid','1',LegacyGridStrategy.requirements,LegacyGridStrategy))
    scheduler.store_factory=lambda category:open_market_store(tmp_path/category/'unused.sqlite3',tmp_path/category/'shards')
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000)
    for _ in range(6):scheduler.tick()
    jobs={j['payload']['strategy_id']:j for j in state.jobs()}
    assert all(j['state']=='COMPLETED' for j in jobs.values()),jobs
    assert jobs['legacy_grid']['result']['output']['candles_processed']==3
    assert 'variants' in jobs['legacy_grid']['result']['output']

def test_different_timeframes_use_distinct_closed_windows(tmp_path):
    req=(DataRequirement('candles',('1m','5m'),min_observations=1),)
    scheduler,state,_,_,_=setup(tmp_path,requirements=req)
    scheduler.discover();keys=scheduler.plan(start_ms=0,end_ms=360000)
    planned=state.get(keys[0])['payload']['requirements']
    assert {r['timeframe']:r['end_ms'] for r in planned}=={'1m':300000,'5m':0}
    for _ in range(9):scheduler.tick()
    assert state.get(keys[0])['state']=='COMPLETED'


def test_selected_same_partition_strategies_progress_without_competing_claims(tmp_path, monkeypatch):
    # Force the old dispatcher race: the first granted lease remains visible
    # until a competing selected worker tries it (or the bounded wait expires
    # when a single partition worker correctly owns the queue).
    scheduler,state,_,registry,_=setup(tmp_path,empty={'ALPHAUSDT'})
    registry.register(StrategyDefinition('second-count','1',
        (DataRequirement('candles',('1m',)),),Count))
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000)
    original=state.claim;guard=threading.Lock();first=[None];competing=threading.Event()
    def controlled_claim(key,*args,**kwargs):
        token=original(key,*args,**kwargs)
        with guard:
            lead=token is not None and first[0] is None
            if lead:first[0]=key
            elif token is None and first[0] is not None:competing.set()
        if lead:competing.wait(.5)
        return token
    monkeypatch.setattr(state,'claim',controlled_claim)
    scheduler.tick()
    jobs=state.jobs()
    assert len(jobs)==2
    assert all(job['state']=='PARTIAL' for job in jobs)
    assert not competing.is_set(), 'same partition must not race its own selected lease'
    assert all(job['result'] is None and job['lease_until'] is None for job in jobs)
