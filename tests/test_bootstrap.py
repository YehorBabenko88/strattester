import sqlite3
from strattester.bootstrap import bootstrap

def legacy_db(path):
    path.parent.mkdir(parents=True)
    c=sqlite3.connect(path)
    c.execute('create table candles(symbol text,timeframe text,open_time integer,open real,high real,low real,close real,volume real)')
    c.execute("insert into candles values('BTCUSDT','1m',1,1,1,1,1,1)")
    c.commit();c.close()

def test_bootstrap_selects_valid_legacy_without_copying(tmp_path):
    legacy=tmp_path/'legacy'/'bybit_1m.sqlite3'; legacy_db(legacy)
    root=tmp_path/'ProgramData'/'Strattester'
    r=bootstrap(root,[legacy])
    assert r.market_db==legacy and r.mode=='legacy-readonly'
    assert not (root/'data'/'bybit_1m.sqlite3').exists()
    assert r.state_db.exists()

def test_bootstrap_does_not_create_empty_market_db(tmp_path):
    root=tmp_path/'ProgramData'/'Strattester'
    r=bootstrap(root,[])
    assert r.market_db is None and r.mode=='empty'
    assert not (root/'data'/'bybit_1m.sqlite3').exists()
