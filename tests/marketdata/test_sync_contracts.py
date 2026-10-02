from strattester.marketdata.sync_engine import DataRequirement,SyncEngine,SyncState
from strattester.marketdata.sqlite_store import SQLiteMarketStore

def test_funding_requirement_uses_client_funding_method(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    class C:
        def fetch_funding(self,symbol,start,end):
            return [{'fundingRateTimestamp':'0','fundingRate':'0.0001'}]
    r=SyncEngine(s,C(),clock_ms=lambda:1_000_000).sync_requirement(
        DataRequirement('BTCUSDT','funding','480m',0,0))
    assert r.state is SyncState.READY
    s.close()

def test_public_trade_aggregate_is_not_silently_faked_from_recent_rest(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    class C: pass
    r=SyncEngine(s,C(),clock_ms=lambda:1_000_000).sync_requirement(
        DataRequirement('BTCUSDT','public_trade_aggregates','1m',0,60_000))
    assert r.state is SyncState.REPAIR_REQUIRED
    assert 'archive' in r.message.lower()
    s.close()
