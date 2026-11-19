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

def test_unverified_grid_universe_cannot_mutate_legacy_registry(tmp_path):
    import pytest
    from strattester.marketdata.universe_sync import UniverseSnapshotError

    db = tmp_path / "i.db"
    reg = InstrumentRegistry.open(db)
    try:
        # Preserve previously persisted history and two active instruments.
        reg.reconcile({"AUSDT", "BUSDT"}, 1000)
        before = list(reg.conn.iterdump())
        sync = UniverseSynchronizer(reg)
        forged = {
            "api_version": "grid.instrument.snapshot.v1",
            "producer": "bybit-cluster-grid",
            "source_qualified": True,  # A caller-controlled boolean is NOT proof.
            "complete": True,
            "history_coverage": "ATTESTED",
            "source_provenance": "ATTESTED",
            "observed_at_ms": 2000,
            "symbols": ["BUSDT"],  # Would mark AUSDT missing if trusted.
        }
        for candidate in (None, forged, {"symbols": []}, {
            "api_version": {"major": 1, "minor": 0},
            "producer": "bybit-cluster-grid",
            "source_provenance": "NOT_ATTESTED",
            "history_coverage": "NOT_ATTESTED",
            "status": "INFORMATIONAL",
        }):
            with pytest.raises(UniverseSnapshotError,
                               match="GRID_VERIFIED_UNIVERSE_API_UNAVAILABLE"):
                sync.sync(2000, snapshot=candidate)
            assert list(reg.conn.iterdump()) == before
        assert reg.active_symbols() == {"AUSDT", "BUSDT"}
        assert reg.get("AUSDT").status is InstrumentStatus.ACTIVE
    finally:
        reg.close()

    reopened = InstrumentRegistry.open(db)
    try:
        assert reopened.active_symbols() == {"AUSDT", "BUSDT"}
        assert reopened.eligible_at("AUSDT", 1500)
    finally:
        reopened.close()


def test_legacy_client_is_refused_without_network_or_mutation(tmp_path):
    import pytest
    from strattester.marketdata.universe_sync import UniverseSnapshotError

    class ForbiddenClient:
        def fetch_linear_symbols(self):
            raise AssertionError("Strattester may not contact Bybit")

    reg = InstrumentRegistry.open(tmp_path / "i.db")
    try:
        before = list(reg.conn.iterdump())
        with pytest.raises(UniverseSnapshotError,
                           match="DIRECT_EXCHANGE_CLIENT_FORBIDDEN"):
            UniverseSynchronizer(reg, client=ForbiddenClient())
        assert list(reg.conn.iterdump()) == before
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
