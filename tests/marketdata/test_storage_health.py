from pathlib import Path
import os
from strattester.marketdata.storage_health import storage_health,quarantine_database,sqlite_footprint,safe_checkpoint
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_storage_health_accepts_writable_database(tmp_path):
    path=tmp_path/'m.db'
    s=SQLiteMarketStore.open(path)
    s.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    s.close()
    h=storage_health(path,min_free_bytes=1)
    assert h.ok and h.writable and h.integrity_ok

def test_storage_health_blocks_when_free_space_threshold_is_impossible(tmp_path):
    h=storage_health(tmp_path,min_free_bytes=10**30)
    assert not h.ok and not h.writable
    assert 'disk space' in h.message

def test_corrupt_database_is_quarantined_not_overwritten(tmp_path):
    path=tmp_path/'m.db'
    path.write_bytes(b'not a sqlite database')
    h=storage_health(path,min_free_bytes=1)
    assert not h.ok and not h.integrity_ok
    target=quarantine_database(path,tmp_path/'quarantine')
    assert not path.exists()
    assert target.exists()
    assert target.read_bytes()==b'not a sqlite database'


def test_sqlite_footprint_counts_wal_sidecars(tmp_path):
    p=tmp_path/'x.db';p.write_bytes(b'123');Path(str(p)+'-wal').write_bytes(b'45')
    assert sqlite_footprint(p)==5

def test_safe_checkpoint_refuses_low_headroom_without_touching_db():
    class C:
        def execute(self,*a):raise AssertionError('checkpoint must not run')
    ok,msg=safe_checkpoint(C(),free_bytes=10,db_footprint=100,minimum_headroom=50)
    assert not ok and 'headroom' in msg

def test_safe_checkpoint_runs_passive_with_headroom():
    class C:
        def __init__(self):self.sql=None
        def execute(self,sql):self.sql=sql;return self
        def fetchone(self):return (0,0,0)
    c=C();ok,row=safe_checkpoint(c,free_bytes=1000,db_footprint=100,minimum_headroom=50)
    assert ok and row==(0,0,0) and c.sql=='PRAGMA wal_checkpoint(PASSIVE)'
