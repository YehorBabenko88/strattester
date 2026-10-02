import sqlite3
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_store_reuses_legacy_ts_candle_database_without_copy(tmp_path):
    p=tmp_path/'legacy.db'
    c=sqlite3.connect(p)
    c.execute('CREATE TABLE candles(symbol TEXT NOT NULL, ts INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL, turnover REAL NOT NULL, PRIMARY KEY(symbol,ts))')
    c.execute("INSERT INTO candles VALUES('BTCUSDT',0,100,101,99,100,10,1000)")
    c.commit(); c.close()
    s=SQLiteMarketStore.open(p)
    cov=s.coverage('BTCUSDT','candles','1m',60_000)
    assert cov.count==1 and cov.earliest==0
    row=next(s.iter_candles('BTCUSDT'))
    assert row.open_time==0 and row.timeframe=='1m'
    stats=s.upsert_candles([Candle('BTCUSDT','1m',60_000,100,102,99,101,11,1100,True)])
    assert stats.accepted==1
    assert s.coverage('BTCUSDT','candles','1m',60_000).count==2
    s.close()

def test_legacy_store_rejects_non_1m_candle_write(tmp_path):
    p=tmp_path/'legacy.db'
    c=sqlite3.connect(p)
    c.execute('CREATE TABLE candles(symbol TEXT NOT NULL, ts INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL, turnover REAL NOT NULL, PRIMARY KEY(symbol,ts))')
    c.commit(); c.close()
    s=SQLiteMarketStore.open(p)
    stats=s.upsert_candles([Candle('BTCUSDT','5m',0,100,101,99,100,1,100,True)])
    assert stats.rejected==1
    s.close()
