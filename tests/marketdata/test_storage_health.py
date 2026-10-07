import os
from strattester.marketdata.storage_health import storage_health,quarantine_database
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
