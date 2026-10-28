"""Real registry/storage integration with synthetic HTTP, never physical ML."""
from dataclasses import replace
import pytest
from strattester.engine.executor import execute_strategy
from strattester.marketdata.bybit_client import BybitClient, BybitResponseError
from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.sqlite_store import Candle
from strattester.strategies.base import StrategyDefinition
from strattester.strategies.builtin.legacy_grid import LegacyGridStrategy
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from tests.engine.test_data_first_scheduler import setup, Transport


def test_bybit_redirect_never_expands_approved_network_scope():
    class Redirect:
        status_code=302;headers={'Location':'https://unapproved.invalid/'};closed=False
        def json(self):return {'retCode':0,'result':{}}
        def close(self):self.closed=True
    response=Redirect();calls=[]
    class Session:
        def get(self,*args,**kwargs):calls.append(kwargs);return response
    with pytest.raises(BybitResponseError):
        BybitClient(session=Session()).get('/v5/market/instruments-info')
    assert calls[0]['allow_redirects'] is False and response.closed


@pytest.mark.parametrize('cursor', [False, 0, [], {}, None])
def test_malformed_terminal_cursor_never_publishes_universe(tmp_path, monkeypatch, cursor):
    scheduler, state, _, _, _ = setup(tmp_path)
    original = Transport.get
    def malformed(self, url, params, timeout, **kwargs):
        response = original(self, url, params, timeout, **kwargs)
        response.data['result']['nextPageCursor'] = cursor
        return response
    monkeypatch.setattr(Transport, 'get', malformed)
    with pytest.raises(BybitResponseError):
        scheduler.discover()
    assert state.instruments() == []


def test_universe_missing_market_identity_never_publishes(tmp_path, monkeypatch):
    scheduler, state, _, _, _ = setup(tmp_path)
    original = Transport.get
    def malformed(self, url, params, timeout, **kwargs):
        response = original(self, url, params, timeout, **kwargs)
        del response.data['result']['category']
        return response
    monkeypatch.setattr(Transport, 'get', malformed)
    with pytest.raises(BybitResponseError):
        scheduler.discover()
    assert state.instruments() == []


def test_explicit_existing_shard_acknowledgement_survives_reopen(tmp_path):
    root = tmp_path/'historical-fixture'
    store = ShardedMarketStore(root)
    store.for_symbol('ALTUSDC').upsert_candles([Candle('ALTUSDC', '1m', 0, 1, 1, 1, 1, 1)])
    store.close()
    store = ShardedMarketStore(root)
    try:
        store.bind_market_category('linear', acknowledge_existing=True)
        assert len(list(store.for_symbol('ALTUSDC').iter_candles('ALTUSDC'))) == 1
    finally:
        store.close()
    store = ShardedMarketStore(root)
    try:
        store.bind_market_category('linear')
        assert len(list(store.for_symbol('ALTUSDC').iter_candles('ALTUSDC'))) == 1
        with pytest.raises(ValueError):
            store.bind_market_category('spot', acknowledge_existing=True)
    finally:
        store.close()


def test_conflicting_shard_category_cannot_commit_root_acknowledgement(tmp_path):
    store = ShardedMarketStore(tmp_path/'conflicting')
    try:
        shard = store.for_symbol('ALTUSDC')
        shard.bind_market_category('spot')
        shard.upsert_candles([Candle('ALTUSDC', '1m', 0, 1, 1, 1, 1, 1)])
        with pytest.raises(ValueError):
            store.bind_market_category('linear', acknowledge_existing=True)
        assert store.manifest.con.execute("SELECT value FROM market_identity WHERE key='category'").fetchone() is None
        assert shard.connection.execute("SELECT value FROM schema_meta WHERE key='market_category'").fetchone()[0] == 'spot'
    finally:
        store.close()


def test_existing_acknowledgement_does_not_bless_later_unbound_shard(tmp_path):
    root=tmp_path/'history'
    store=ShardedMarketStore(root)
    try:
        store.bind_market_category('linear',acknowledge_existing=True)
        incoming=SQLiteMarketStore.open(store.shard_path('UNTRUSTED'))
        incoming.upsert_candles([Candle('UNTRUSTED','1m',0,1,1,1,1,1)]);incoming.close()
        with pytest.raises(ValueError,match='provenance'):
            store.for_symbol('UNTRUSTED')
    finally:store.close()


def test_real_financial_registry_stays_disabled_and_enabled_candle_path_is_blocked(tmp_path, monkeypatch):
    from strattester.strategies.builtin import financial_structural as financial
    # Mutation target: generic execution must never call signed inference.
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError('financial inference not authorized by candle readiness')
    monkeypatch.setattr(financial, 'run_attested_offline', forbidden)
    scheduler, state, network, registry, _ = setup(tmp_path)
    definition = financial.register_financial_research(registry, research_only=True)
    scheduler.discover()
    first = scheduler.plan(start_ms=0, end_ms=60000)
    assert len(first) == 1 and definition.enabled is False
    with pytest.raises(ValueError, match='disabled'):
        execute_strategy(definition, object(), 'ALTUSDC')
    registry.set_enabled(definition.id, definition.version, True)
    scheduler.plan(start_ms=0, end_ms=60000)
    scheduler.tick();scheduler.tick()
    job = next(j for j in state.jobs() if j['payload']['strategy_id'] == definition.id)
    assert job['state'] == 'BLOCKED' and job['result'] is None
    assert 'NO_DECLARED_REQUIREMENTS' in job['reason']
    with pytest.raises(ValueError, match='context'):
        execute_strategy(replace(definition, enabled=True), object(), 'ALTUSDC')
    assert calls == []


def test_real_legacy_partial_instrument_and_restart_do_not_duplicate_result(tmp_path):
    rows={'linear':[{'symbol':s,'status':'Trading','launchTime':'0'} for s in ('READYUSDC','PARTIALUSDT')]}
    scheduler,state,network,registry,stores=setup(tmp_path,rows=rows,empty={'PARTIALUSDT'})
    registry.register(StrategyDefinition(LegacyGridStrategy.id,LegacyGridStrategy.version,
        LegacyGridStrategy.requirements,LegacyGridStrategy))
    store=stores('linear')
    store.upsert_candles([Candle('READYUSDC','1m',t,100,101,99,100,1) for t in (0,60000,120000)])
    store.close()
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000)
    scheduler.tick();scheduler.tick()
    ready=next(j for j in state.jobs() if j['payload']['strategy_id']==LegacyGridStrategy.id and j['payload']['instrument']['symbol']=='READYUSDC')
    assert ready['state']=='COMPLETED' and ready['result']['output']['candles_processed']==3
    assert all(j['state']=='PARTIAL' for j in state.jobs() if j['payload']['instrument']['symbol']=='PARTIALUSDT')
    before=ready['result'];old_events=len(state.events(ready['id']))
    scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
    assert state.get(ready['id'])['result']==before and len(state.events(ready['id']))==old_events
    assert not any(p.get('symbol')=='READYUSDC' for u,p in network if u.endswith('kline'))


def legacy_only(registry):
    registry.set_enabled('count','1',False)
    registry.register(StrategyDefinition(LegacyGridStrategy.id,LegacyGridStrategy.version,
        LegacyGridStrategy.requirements,LegacyGridStrategy))


def test_real_legacy_delisted_archive_excludes_inactive_gap(tmp_path):
    scheduler,state,network,registry,_=setup(tmp_path)
    legacy_only(registry)
    state.register_history('linear',{'symbol':'DEADUSDC','status':'Closed','launchTime':'0','deliveryTime':'300000'},
        [(0,120000),(180000,300000)],source_sha256='a'*64,observed_at=600000)
    scheduler.plan(start_ms=0,end_ms=600000)
    for _ in range(6):scheduler.tick()
    assert len(state.jobs())==2 and all(j['state']=='COMPLETED' for j in state.jobs())
    assert [j['result']['output']['candles_processed'] for j in state.jobs()]==[2,2]
    assert all(not p['start']<=120000<=p['end'] for u,p in network if u.endswith('kline'))


def test_real_legacy_snapshot_survives_concurrent_delete_before_backtest(tmp_path,monkeypatch):
    scheduler,state,network,registry,stores=setup(tmp_path)
    legacy_only(registry)
    writer=stores('linear')
    writer.upsert_candles([Candle('ALPHAUSDT','1m',t,100,101,99,100,1) for t in (0,60000,120000)])
    validate=SQLiteMarketStore.validate_range;deleted=[]
    def racing(self,*args):
        ready=validate(self,*args)
        if self.research_snapshot_active and not deleted:
            other=SQLiteMarketStore.open(self.path)
            try:
                other.connection.execute('DELETE FROM candles');other.connection.commit();deleted.append(True)
            finally:other.close()
        return ready
    monkeypatch.setattr(SQLiteMarketStore,'validate_range',racing)
    try:
        scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000);scheduler.tick()
        job=state.jobs()[0]
        assert deleted==[True] and writer.connection.execute('SELECT COUNT(*) FROM candles').fetchone()[0]==0
        assert job['state']=='COMPLETED' and job['result']['output']['candles_processed']==3
        assert not any(u.endswith('kline') for u,p in network)
    finally:writer.close()


def test_real_legacy_cancel_after_backtest_never_publishes_or_replays(tmp_path,monkeypatch):
    flag=[False];scheduler,state,_,registry,stores=setup(tmp_path,cancel=lambda:flag[0])
    legacy_only(registry)
    store=stores('linear');store.upsert_candles([Candle('ALPHAUSDT','1m',0,100,101,99,100,1)]);store.close()
    original=LegacyGridStrategy.run;calls=[]
    def interrupted(self,candles,checkpoint=None):
        result=original(self,candles,checkpoint=checkpoint);calls.append(1);flag[0]=True
        return result
    monkeypatch.setattr(LegacyGridStrategy,'run',interrupted)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=60000);scheduler.tick()
    job=state.jobs()[0]
    assert job['state']=='BLOCKED' and job['result'] is None and calls==[1]
    flag[0]=False
    scheduler.tick()
    assert state.get(job['id'])['result'] is None and calls==[1]
