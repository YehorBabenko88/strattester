from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

def test_sync_engine_persists_mark_price_history(tmp_path):
    class C:
        def fetch_mark_klines(self,symbol,start,end,interval='1'):
            rows=[['0','100','101','99','100'],['60000','100','102','99','101']]
            return [r for r in reversed(rows) if start<=int(r[0])<=end]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,C(),clock_ms=lambda:999999).sync_requirement(DataRequirement('BTCUSDT','mark_price','1m',0,60000))
    assert r.state is SyncState.READY
    assert s.coverage('BTCUSDT','mark_price','1m').count==2
    s.close()

def test_sync_engine_persists_open_interest_history(tmp_path):
    class C:
        def fetch_open_interest(self,symbol,start,end,interval='5min'):
            return [{'timestamp':'0','openInterest':'100'},{'timestamp':'300000','openInterest':'110'}]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,C(),clock_ms=lambda:9999999).sync_requirement(DataRequirement('BTCUSDT','open_interest','5m',0,300000))
    assert r.state is SyncState.READY
    assert s.coverage('BTCUSDT','open_interest','5m',300000).count==2
    s.close()
