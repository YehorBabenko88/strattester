from pathlib import Path
import sqlite3
from strattester.marketdata.readiness import open_market_store,ensure_history,requirements_for_instrument,dataset_capabilities
from strattester.marketdata.sync_engine import DataRequirement,SyncState

def _legacy(path):
    c=sqlite3.connect(path)
    c.execute('CREATE TABLE candles(symbol TEXT NOT NULL, ts INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL, turnover REAL NOT NULL, PRIMARY KEY(symbol,ts))')
    c.execute("INSERT INTO candles VALUES('BTCUSDT',0,100,101,99,100,1,100)")
    c.commit(); c.close()

def test_open_market_store_prefers_existing_local_legacy_data(tmp_path):
    root=tmp_path/'app'; root.mkdir()
    legacy=tmp_path/'legacy.db'; _legacy(legacy)
    opened=open_market_store(root,legacy_paths=(legacy,))
    assert opened.path==legacy
    assert opened.store.coverage('BTCUSDT','candles','1m').count==1
    opened.store.close()

def test_open_market_store_creates_canonical_db_only_when_nothing_exists(tmp_path):
    root=tmp_path/'app'; root.mkdir()
    opened=open_market_store(root,legacy_paths=())
    assert opened.path==root/'data'/'bybit_1m.sqlite3'
    assert opened.path.exists()
    opened.store.close()

def test_ensure_history_downloads_only_missing_ranges(tmp_path):
    root=tmp_path/'app'; root.mkdir()
    opened=open_market_store(root,legacy_paths=())
    class C:
        calls=[]
        def fetch_klines(self,symbol,start,end,interval='1'):
            self.calls.append((symbol,start,end,interval))
            rows=[['0','100','101','99','100','1','100'],['60000','100','102','99','101','1','101']]
            return [r for r in reversed(rows) if start<=int(r[0])<=end]
    client=C()
    req=DataRequirement('BTCUSDT','candles','1m',0,60_000)
    first=ensure_history(opened.store,client,(req,),clock_ms=lambda:999_999)
    assert first[0].state is SyncState.READY
    calls_after_first=len(client.calls)
    second=ensure_history(opened.store,client,(req,),clock_ms=lambda:999_999)
    assert second[0].state is SyncState.READY
    assert len(client.calls)==calls_after_first
    opened.store.close()


def test_requirements_skip_explicitly_unsupported_optional_datasets():
    instrument={"symbol":"NEWUSDT","launchTime":"60000","fundingInterval":None,
                "supportsOpenInterest":False,"supportsFunding":False,"supportsLongShortRatio":False}
    caps=dataset_capabilities(instrument)
    req=requirements_for_instrument(instrument,end_ms=600000)
    datasets={x.dataset for x in req}
    assert datasets=={"candles","mark_price","index_price","premium_index"}
    assert "open_interest" not in caps and "funding" not in caps

def test_supported_optional_datasets_remain_required():
    instrument={"symbol":"BTCUSDT","launchTime":"0","fundingInterval":"480",
                "supportsOpenInterest":True,"supportsFunding":True,"supportsLongShortRatio":True}
    assert {x.dataset for x in requirements_for_instrument(instrument,end_ms=600000)}=={
        "candles","mark_price","index_price","premium_index","open_interest","funding","long_short_ratio"}
