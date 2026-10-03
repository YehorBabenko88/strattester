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


def test_candle_sync_uses_requested_native_bybit_interval(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    seen=[]
    class C:
        def fetch_klines(self,symbol,start,end,interval):
            seen.append(interval)
            return [['0','1','1','1','1','1','1']]
    r=SyncEngine(s,C(),clock_ms=lambda:10_000_000).sync_requirement(
        DataRequirement('BTCUSDT','candles','5m',0,0))
    assert r.state is SyncState.READY
    assert seen==['5']
    assert list(s.iter_candles('BTCUSDT','5m'))[0].open_time==0
    s.close()
