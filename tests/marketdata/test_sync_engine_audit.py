from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement,SyncState

def row(t):
    return [str(t),'1','1.1','.9','1','10','100']

class Client:
    def __init__(self,rows): self.rows=rows; self.calls=[]
    def fetch_klines(self,symbol,start,end,interval):
        self.calls.append((start,end,interval))
        return [r for r in self.rows if start<=int(r[0])<=end]

def test_sync_repairs_missing_left_and_right_edges(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([Candle('BTCUSDT','1m',60000,1,1,1,1,1)])
    c=Client([row(0),row(120000)])
    r=SyncEngine(s,c,clock_ms=lambda:999999).sync_requirement(
        DataRequirement('BTCUSDT','candles','1m',0,120000))
    assert r.state==SyncState.READY
    cov=s.coverage('BTCUSDT','candles','1m',start_ms=0,end_ms=120000)
    assert cov.count==3 and not cov.gaps
    s.close()

def test_sync_aligns_unaligned_range_to_native_timeframe(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    c=Client([row(300000),row(600000)])
    r=SyncEngine(s,c,clock_ms=lambda:9999999).sync_requirement(
        DataRequirement('BTCUSDT','candles','5m',60000,660000))
    assert r.state==SyncState.READY
    assert c.calls[0][:2]==(300000,600000)
    cov=s.coverage('BTCUSDT','candles','5m',start_ms=60000,end_ms=660000,step_ms=300000)
    assert (cov.earliest,cov.latest,cov.count)==(300000,600000,2)
    s.close()

def test_local_public_trade_archive_can_be_ready_without_rest_sync(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_public_trade_aggregates('BTCUSDT',[
        {'open_time':0,'buy_volume':1,'sell_volume':0,'turnover':1,'trade_count':1},
        {'open_time':60000,'buy_volume':1,'sell_volume':0,'turnover':1,'trade_count':1},
    ])
    r=SyncEngine(s,object()).sync_requirement(
        DataRequirement('BTCUSDT','public_trade_aggregates','1m',0,60000))
    assert r.state==SyncState.READY
    s.close()
