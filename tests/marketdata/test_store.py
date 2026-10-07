import sqlite3
import pytest
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def c(t=0,complete=True,close=1.0):
    return Candle('BTCUSDT','1m',t,1.0,1.1,0.9,close,10.0,100.0,complete)

def test_candle_insert_shape_is_ten_columns():
    candle=c()
    assert len((candle.symbol,candle.timeframe,candle.open_time,candle.open,candle.high,candle.low,candle.close,candle.volume,candle.turnover,int(candle.complete)))==10

def test_duplicate_is_idempotent(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    assert s.upsert_candles([c()]).accepted==1
    stats=s.upsert_candles([c()])
    assert stats.unchanged==1
    assert s.coverage('BTCUSDT').count==1
    s.close()

def test_complete_record_repairs_incomplete(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    s.upsert_candles([c(complete=False,close=.95)])
    assert s.upsert_candles([c(complete=True,close=1.0)]).accepted==1
    assert list(s.iter_candles('BTCUSDT'))[0].complete is True
    s.close()

def test_incomplete_cannot_regress_complete(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db'); s.upsert_candles([c()])
    assert s.upsert_candles([c(complete=False,close=.95)]).rejected==1
    s.close()

def test_malformed_candle_rejected(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    bad=Candle('BTCUSDT','1m',0,2,1,0,1,1)
    assert s.upsert_candles([bad]).rejected==1
    s.close()

def test_transaction_rolls_back_on_sql_error(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    class Broken:
        def __iter__(self): return iter([c(0), c(60_000)])
    s.connection.execute('DROP TABLE candles')
    with pytest.raises(sqlite3.Error):
        s.upsert_candles(Broken())
    s.close()


def test_generator_failure_rolls_back_whole_candle_batch(tmp_path):
    s=SQLiteMarketStore.open(tmp_path/'m.db')
    def broken():
        yield c(0)
        raise RuntimeError('simulated process interruption')
    with pytest.raises(RuntimeError):
        s.upsert_candles(broken())
    assert s.coverage('BTCUSDT').count==0
    assert s.integrity_check()
    s.close()

def test_two_local_connections_can_write_different_symbols_without_corruption(tmp_path):
    import threading
    path=tmp_path/'m.db'
    seed=SQLiteMarketStore.open(path); seed.close()
    errors=[]
    def write(symbol):
        store=None
        try:
            store=SQLiteMarketStore.open(path)
            rows=[Candle(symbol,'1m',i*60_000,1,1.1,.9,1,1) for i in range(100)]
            store.upsert_candles(rows)
        except Exception as exc:
            errors.append(exc)
        finally:
            if store is not None: store.close()
    t1=threading.Thread(target=write,args=('BTCUSDT',))
    t2=threading.Thread(target=write,args=('ETHUSDT',))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not errors
    check=SQLiteMarketStore.open(path)
    assert check.coverage('BTCUSDT').count==100
    assert check.coverage('ETHUSDT').count==100
    assert check.integrity_check()
    check.close()

def test_wal_checkpoint_and_reopen_preserve_integrity(tmp_path):
    path=tmp_path/'m.db'
    s=SQLiteMarketStore.open(path)
    s.upsert_candles([c(i*60_000) for i in range(10)])
    s.checkpoint_wal('FULL')
    s.close()
    reopened=SQLiteMarketStore.open(path)
    assert reopened.coverage('BTCUSDT').count==10
    assert reopened.integrity_check()
    reopened.close()
