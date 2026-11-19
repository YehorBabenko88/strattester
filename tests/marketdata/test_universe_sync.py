from strattester.marketdata.bybit_client import BybitClient
from strattester.marketdata.instruments import InstrumentRegistry,InstrumentStatus
from strattester.marketdata.universe_sync import UniverseSynchronizer
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

class PayloadResponse:
    status_code=200
    def __init__(self,payload): self.payload=payload
    def json(self): return self.payload
class PayloadSession:
    def __init__(self,payload): self.payload=payload
    def get(self,*a,**k): return PayloadResponse(self.payload)

def test_bybit_discovers_only_trading_usdt_linear_perpetuals():
    payload={'retCode':0,'result':{'list':[
      {'symbol':'BTCUSDT','status':'Trading','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'OLDUSDT','status':'Settled','quoteCoin':'USDT','contractType':'LinearPerpetual'},
      {'symbol':'BTCUSDC','status':'Trading','quoteCoin':'USDC','contractType':'LinearPerpetual'}]}}
    c=BybitClient(session=PayloadSession(payload))
    assert c.fetch_linear_symbols()=={'BTCUSDT'}

def grid_snapshot(symbols, observed_at, **overrides):
    return {
        "api_version": "grid.instrument.snapshot.v1",
        "source_qualified": True,
        "complete": True,
        "observed_at_ms": observed_at,
        "symbols": sorted(symbols),
        **overrides,
    }


def test_universe_sync_retains_disappeared_instrument(tmp_path):
    reg = InstrumentRegistry.open(tmp_path / 'i.db')
    try:
        u = UniverseSynchronizer(reg)
        u.sync(1000, snapshot=grid_snapshot({'AUSDT', 'BUSDT'}, 1000))
        u.sync(2000, snapshot=grid_snapshot({'BUSDT'}, 2000))
        assert reg.get('AUSDT').status is InstrumentStatus.MISSING
        u.sync(3000, snapshot=grid_snapshot({'BUSDT'}, 3000))
        assert reg.get('AUSDT').status is InstrumentStatus.DELISTED
        assert reg.eligible_at('AUSDT', 1500)
    finally:
        reg.close()


def test_unqualified_snapshot_and_client_have_no_mutation(tmp_path):
    from strattester.marketdata.universe_sync import UniverseSnapshotError
    import pytest
    reg = InstrumentRegistry.open(tmp_path / 'i.db')
    try:
        u = UniverseSynchronizer(reg)
        u.sync(1000, snapshot=grid_snapshot({'AUSDT', 'BUSDT'}, 1000))
        before = list(reg.conn.iterdump())
        for invalid in (
            None,
            grid_snapshot({'AUSDT'}, 2000, source_qualified=False),
            grid_snapshot({'AUSDT'}, 2000, complete=False),
            grid_snapshot({'AUSDT'}, 2000, api_version="unverified"),
            grid_snapshot({'AUSDT'}, 3000),
            grid_snapshot(set(), 2000),
            grid_snapshot({'AUSDT'}, 2000, symbols=[None]),
        ):
            with pytest.raises(UniverseSnapshotError):
                u.sync(2000, snapshot=invalid)
            assert list(reg.conn.iterdump()) == before
        with pytest.raises(UniverseSnapshotError, match="GRID_SNAPSHOT_REQUIRED"):
            UniverseSynchronizer(reg, client=object())
        assert list(reg.conn.iterdump()) == before
    finally:
        reg.close()


def test_empty_exchange_snapshot_does_not_mass_delist(tmp_path):
    from strattester.marketdata.universe_sync import UniverseSnapshotError
    import pytest
    reg = InstrumentRegistry.open(tmp_path / 'i.db')
    try:
        u = UniverseSynchronizer(reg)
        u.sync(1000, snapshot=grid_snapshot({'AUSDT', 'BUSDT'}, 1000))
        with pytest.raises(UniverseSnapshotError):
            u.sync(2000, snapshot=grid_snapshot(set(), 2000))
        assert reg.active_symbols() == {'AUSDT', 'BUSDT'}
    finally:
        reg.close()


def test_reverse_chronological_pages_do_not_skip_middle(tmp_path):
    def row(t): return [str(t),'1','1.1','.9','1','10','100']
    class ReversePaged:
        def __init__(self): self.calls=[]
        def fetch_klines(self,symbol,start,end,interval='1',limit=1000):
            self.calls.append((start,end))
            all_rows=[row(0),row(60000),row(120000),row(180000),row(240000)]
            eligible=[r for r in all_rows if start<=int(r[0])<=end]
            return list(reversed(eligible))[:2]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,ReversePaged(),clock_ms=lambda:999999).sync_requirement(DataRequirement('BTCUSDT',start_ms=0,end_ms=240000))
    assert r.state is SyncState.READY
    assert s.coverage('BTCUSDT').count==5
    s.close()
