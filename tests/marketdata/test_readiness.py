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


def test_requirements_stop_at_delisting_boundary():
    instrument={"symbol":"OLDUSDT","launchTime":"60000","deliveryTime":"600000",
                "fundingInterval":"480","supportsOpenInterest":True,"supportsFunding":True}
    req=requirements_for_instrument(instrument,end_ms=900000)
    by={x.dataset:x for x in req}
    assert by['candles'].start_ms==60000 and by['candles'].end_ms==600000
    assert by['open_interest'].start_ms==300000 and by['open_interest'].end_ms==600000
    assert 'funding' not in by  # no complete 480m observation exists inside lifetime

def test_requirements_empty_before_instrument_launch():
    instrument={"symbol":"NEWUSDT","launchTime":"600000","fundingInterval":"480"}
    assert requirements_for_instrument(instrument,end_ms=300000)==()

def test_zero_delivery_time_does_not_truncate_perpetual_instrument():
    instrument={"symbol":"BTCUSDT","launchTime":"0","deliveryTime":"0","fundingInterval":"480"}
    req=requirements_for_instrument(instrument,end_ms=900000)
    by={x.dataset:x for x in req}
    assert by['candles'].end_ms==900000
    assert by['open_interest'].end_ms==900000
    assert by['funding'].end_ms==0


def test_dataset_windows_align_to_their_own_sampling_grid():
    instrument={"symbol":"XUSDT","launchTime":"61000","deliveryTime":"899999",
                "fundingInterval":"8","supportsOpenInterest":True,"supportsFunding":True,
                "supportsLongShortRatio":True}
    req={x.dataset:x for x in requirements_for_instrument(instrument,end_ms=999999)}
    assert req['candles'].start_ms==120000 and req['candles'].end_ms==840000
    assert req['open_interest'].start_ms==300000 and req['open_interest'].end_ms==600000
    assert req['long_short_ratio'].start_ms==300000 and req['long_short_ratio'].end_ms==600000
    assert req['funding'].start_ms==480000 and req['funding'].end_ms==480000
