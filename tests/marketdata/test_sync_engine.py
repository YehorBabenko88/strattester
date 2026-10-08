from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState
from strattester.marketdata.bybit_client import BybitAccessError

from strattester.marketdata.errors import DatasetUnavailableError
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


def test_one_unavailable_dataset_is_isolated_from_other_requirements(tmp_path):
    class C:
        def fetch_klines(self,*a):return [['0','1','1','1','1','1','1']]
        def fetch_open_interest(self,*a):raise DatasetUnavailableError("not available for this symbol")
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    engine=SyncEngine(store,C(),clock_ms=lambda:999999)
    good=engine.sync_requirement(DataRequirement('X','candles','1m',0,0))
    bad=engine.sync_requirement(DataRequirement('X','open_interest','5m',0,0))
    assert good.state is SyncState.READY
    assert bad.state is SyncState.UNAVAILABLE
    store.close()


def test_empty_exchange_page_never_marks_missing_history_ready(tmp_path):
    class C:
        def fetch_klines(self,*a):return []
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    result=SyncEngine(store,C(),clock_ms=lambda:999999).sync_requirement(
        DataRequirement('EMPTY','candles','1m',0,120000))
    assert result.state is SyncState.PARTIAL
    assert "incomplete" in result.message
    assert store.coverage('EMPTY','candles','1m').count==0
    store.close()


def test_open_interest_timestamp_zero_is_not_replaced_by_fallback(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    class C:
        def fetch_open_interest(self,*a,**k):return [{'timestamp':0,'time':999999,'openInterest':'12.5'}]
    req=DataRequirement('BTCUSDT','open_interest','5m',0,0)
    result=SyncEngine(store,C(),clock_ms=lambda:999999).sync_requirement(req)
    assert result.state is SyncState.READY
    assert store.coverage('BTCUSDT','open_interest','5m').earliest==0
    store.close()

def test_auxiliary_row_without_any_timestamp_is_retryable_not_ready(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    class C:
        def fetch_open_interest(self,*a,**k):return [{'openInterest':'12.5'}]
    req=DataRequirement('BTCUSDT','open_interest','5m',0,0)
    result=SyncEngine(store,C(),clock_ms=lambda:999999).sync_requirement(req)
    assert result.state is SyncState.RETRYABLE
    assert store.coverage('BTCUSDT','open_interest','5m').count==0
    store.close()


def test_restart_after_partial_backfill_requests_only_persisted_gap(tmp_path):
    db=tmp_path/'m.db'
    first=SQLiteMarketStore.open(db)
    first.upsert_candles([Candle('BTCUSDT','1m',120000,1,1,1,1,1)])
    first.close()  # committed page survives process/reboot boundary

    client=Client([row(0),row(60000),row(180000),row(240000)])
    reopened=SQLiteMarketStore.open(db)
    req=DataRequirement('BTCUSDT','candles','1m',0,240000)
    result=SyncEngine(reopened,client,clock_ms=lambda:999999).sync_requirement(req)
    assert result.state is SyncState.READY
    # Existing 120000 is not downloaded again: only prefix and suffix gaps.
    assert (0,60000) in client.calls and (180000,240000) in client.calls
    assert all(not (a<=120000<=b) for a,b in client.calls)
    assert reopened.coverage('BTCUSDT','candles','1m').count==5
    assert reopened.integrity_check()
    reopened.close()


def test_hard_crash_mid_market_transaction_recovers_wal_without_phantom_page(tmp_path):
    import os,sqlite3,subprocess,sys
    db=tmp_path/'crash.db'
    store=SQLiteMarketStore.open(db)
    store.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    store.close()
    script=r"""
import os,sqlite3,sys
c=sqlite3.connect(sys.argv[1])
c.execute('PRAGMA journal_mode=WAL')
c.execute('PRAGMA synchronous=FULL')
c.execute('BEGIN IMMEDIATE')
c.execute("INSERT INTO candles(symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete) VALUES('BTCUSDT','1m',60000,1,1,1,1,1,NULL,1)")
os._exit(41)
"""
    child=subprocess.run([sys.executable,'-c',script,str(db)])
    assert child.returncode==41
    reopened=SQLiteMarketStore.open(db)
    cov=reopened.coverage('BTCUSDT','candles','1m')
    assert cov.count==1 and cov.earliest==0 and cov.latest==0
    assert reopened.integrity_check()
    client=Client([row(60000)])
    result=SyncEngine(reopened,client,clock_ms=lambda:999999).sync_requirement(
        DataRequirement('BTCUSDT','candles','1m',0,60000))
    assert result.state is SyncState.READY
    assert client.calls==[(60000,60000)]
    assert reopened.coverage('BTCUSDT','candles','1m').count==2
    reopened.close()
