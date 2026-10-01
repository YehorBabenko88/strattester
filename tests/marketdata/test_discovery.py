from pathlib import Path
import sqlite3
from strattester.config import AppConfig
from strattester.marketdata.discovery import discover_databases, inspect_database, adopt_database

def make_db(path: Path):
    con = sqlite3.connect(path)
    con.execute('create table candles(symbol text, timeframe text, open_time integer, open real, high real, low real, close real, volume real, primary key(symbol,timeframe,open_time))')
    con.execute("insert into candles values('BTCUSDT','1m',1,1,1,1,1,1)")
    con.commit(); con.close()

def test_missing_candidate_is_not_created(tmp_path):
    p = tmp_path/'missing.sqlite3'
    result = inspect_database(p)
    assert not p.exists()
    assert result.valid is False

def test_valid_db_is_discovered_read_only(tmp_path):
    p=tmp_path/'legacy.sqlite3'; make_db(p)
    cfg=AppConfig.load(tmp_path/'app')
    found=discover_databases(cfg,[p])
    assert found and found[0].path == p
    assert found[0].valid

def test_invalid_large_file_is_rejected(tmp_path):
    p=tmp_path/'bad.sqlite3'; p.write_bytes(b'not sqlite' * 100)
    assert inspect_database(p).valid is False

def test_adoption_never_overwrites_existing_destination(tmp_path):
    src=tmp_path/'src.sqlite3'; dst=tmp_path/'dst.sqlite3'; make_db(src); make_db(dst)
    candidate=discover_databases(AppConfig.load(tmp_path/'app'),[src])[0]
    result=adopt_database(candidate,dst)
    assert result.adopted is False
    assert src.exists() and dst.exists()
