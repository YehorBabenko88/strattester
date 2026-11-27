from pathlib import Path
import pytest
from strattester.marketdata.download_smoke import run_download_smoke


def _row(t):
    return [str(t),'1','1.1','0.9','1','10','100']


class FakeManagedGridReader:
    def __init__(self, rows):
        self.rows=rows
        self.calls=[]

    def fetch_klines(self, symbol,start,end,interval,limit):
        self.calls.append((symbol,start,end,interval,limit))
        return [row for row in self.rows if start<=int(row[0])<=end]


def test_no_implicit_bybit_network_or_user_root_write(tmp_path,monkeypatch):
    root=tmp_path/'user-market-data'
    root.mkdir()
    sentinel=root/'market_download_smoke.sqlite3'
    sentinel.write_bytes(b'USER-DB-KEEP-EXACT')
    def cannot_connect(*a,**kw):
        raise AssertionError('unexpected outbound exchange network')
    import requests
    monkeypatch.setattr(requests,'Session',cannot_connect)
    result=run_download_smoke(root,client=None)
    assert not result.ok and result.detail=='MANAGED_GRID_READER_REQUIRED'
    assert sentinel.read_bytes()==b'USER-DB-KEEP-EXACT'
    assert sorted(p.name for p in root.iterdir())==[sentinel.name]


def test_explicit_grid_reader_only_writes_disposable_db(tmp_path):
    root=tmp_path/'real-user-market-data'
    root.mkdir()
    sentinel=root/'market_download_smoke.sqlite3'
    sentinel.write_bytes(b'PERSISTENT-USER-ORIGINAL')
    now=900_000
    end=((now//60_000)-2)*60_000
    start=end-120_000
    reader=FakeManagedGridReader([_row(start),_row(start+60_000),_row(end)])
    result=run_download_smoke(root,client=reader,minutes=3,clock_ms=lambda:now)
    assert result.ok,result.detail
    assert result.count==3
    assert len(reader.calls)==1 and reader.calls[0][0]=='BTCUSDT'
    assert 'NOT_EXCHANGE_ATTESTED' in result.detail
    assert sentinel.read_bytes()==b'PERSISTENT-USER-ORIGINAL'
    assert sorted(p.name for p in root.iterdir())==[sentinel.name]


def test_gap_fails_without_creating_any_sqlite_in_user_root(tmp_path):
    root=tmp_path/'user-root'
    reader=FakeManagedGridReader([_row(600_000)])
    result=run_download_smoke(root,reader,minutes=3,clock_ms=lambda:900_000)
    assert not result.ok
    assert not root.exists()


@pytest.mark.parametrize('minutes',[0,-1,True,1001,'5'])
def test_invalid_minutes_fail_before_client_or_storage(tmp_path,minutes):
    reader=FakeManagedGridReader([])
    result=run_download_smoke(tmp_path/'user-root',reader,minutes=minutes)
    assert not result.ok and result.detail=='INVALID_SMOKE_MINUTES'
    assert reader.calls==[]
    assert not (tmp_path/'user-root').exists()
