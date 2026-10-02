from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState
from strattester.marketdata.bybit_client import BybitAccessError

class Client:
    def __init__(self,rows): self.rows=rows; self.calls=[]
    def fetch_klines(self,symbol,start,end,interval):
        self.calls.append((start,end))
        return [r for r in self.rows if start<=int(r[0])<=end]

def row(t): return [str(t),'1','1.1','.9','1','10','100']

def test_empty_db_syncs_and_overlap_is_harmless(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db'); c=Client([row(0),row(60000),row(120000)])
    e=SyncEngine(s,c,clock_ms=lambda:999999)
    req=DataRequirement('BTCUSDT',start_ms=0,end_ms=120000)
    assert e.sync_requirement(req).state==SyncState.READY
    assert s.coverage('BTCUSDT').count==3
    assert e.sync_requirement(req).written==0
    s.close()

def test_internal_gap_is_repaired(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1),Candle('BTCUSDT','1m',120000,1,1,1,1,1)])
    e=SyncEngine(s,Client([row(60000)]),clock_ms=lambda:999999)
    assert e.sync_requirement(DataRequirement('BTCUSDT',start_ms=0,end_ms=120000)).state==SyncState.READY
    assert s.coverage('BTCUSDT').count==3
    s.close()

def test_403_degrades_one_requirement(tmp_path):
    class Forbidden:
        def fetch_klines(self,*a,**k): raise BybitAccessError('forbidden')
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    r=SyncEngine(s,Forbidden()).sync_requirement(DataRequirement('BTCUSDT',start_ms=0,end_ms=0))
    assert r.state==SyncState.DEGRADED
    s.close()
