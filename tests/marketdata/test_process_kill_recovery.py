from __future__ import annotations
import subprocess,sys,textwrap
from strattester.marketdata.sqlite_store import SQLiteMarketStore

def _kill_writer(db,commit):
    code=textwrap.dedent(f"""
        import os,sqlite3
        from pathlib import Path
        from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
        s=SQLiteMarketStore.open(Path(r'{str(db)}'))
        s.connection.execute('BEGIN IMMEDIATE')
        s.connection.execute(
            "INSERT INTO candles(symbol,timeframe,open_time,open,high,low,close,volume,turnover,complete) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ('BTCUSDT','1m',60000,1,1,1,1,1,None,1))
        {"s.connection.commit()" if commit else ""}
        os._exit(23)
    """)
    return subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)

def test_os_hard_kill_rolls_back_uncommitted_wal_transaction(tmp_path):
    db=tmp_path/'market.db'
    s=SQLiteMarketStore.open(db); s.close()
    result=_kill_writer(db,False)
    assert result.returncode==23
    reopened=SQLiteMarketStore.open(db)
    assert reopened.coverage('BTCUSDT').count==0
    assert reopened.integrity_check()
    reopened.close()

def test_os_hard_kill_preserves_committed_wal_transaction(tmp_path):
    db=tmp_path/'market.db'
    s=SQLiteMarketStore.open(db); s.close()
    result=_kill_writer(db,True)
    assert result.returncode==23
    reopened=SQLiteMarketStore.open(db)
    assert reopened.coverage('BTCUSDT').count==1
    assert reopened.integrity_check()
    reopened.close()
