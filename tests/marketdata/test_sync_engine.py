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


def test_failover_node_repairs_only_missing_local_history(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'new-node.db')
    s.upsert_candles([
        Candle('BTCUSDT','1m',0,1,1,1,1,1),
        Candle('BTCUSDT','1m',120000,1,1,1,1,1),
    ])
    client=Client([row(60000)])
    result=SyncEngine(s,client,clock_ms=lambda:999999).sync_requirement(
        DataRequirement('BTCUSDT',start_ms=0,end_ms=120000))
    assert result.state is SyncState.READY
    assert client.calls==[(60000,60000)]
    assert s.coverage('BTCUSDT',start_ms=0,end_ms=120000).count==3
    s.close()

def test_retry_after_interrupted_page_is_idempotent(tmp_path):
    class InterruptOnce(Client):
        def __init__(self,rows):
            super().__init__(rows); self.failed=False
        def fetch_klines(self,symbol,start,end,interval):
            self.calls.append((start,end))
            if not self.failed:
                self.failed=True
                raise ConnectionError('simulated node/network loss')
            return [r for r in self.rows if start<=int(r[0])<=end]
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    client=InterruptOnce([row(0),row(60000),row(120000)])
    engine=SyncEngine(s,client,clock_ms=lambda:999999)
    req=DataRequirement('BTCUSDT',start_ms=0,end_ms=120000)
    first=engine.sync_requirement(req)
    assert first.state is SyncState.RETRYABLE
    second=engine.sync_requirement(req)
    assert second.state is SyncState.READY
    assert s.coverage('BTCUSDT').count==3
    assert s.integrity_check()
    s.close()
