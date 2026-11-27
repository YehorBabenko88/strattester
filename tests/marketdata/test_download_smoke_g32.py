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


def test_managed_reader_exception_fails_closed_without_storage(tmp_path):
    class BrokenReader:
        def fetch_klines(self, *args, **kwargs):
            raise ConnectionError("no managed source")
    root = tmp_path / "user-root"
    result = run_download_smoke(root, BrokenReader(), minutes=3, clock_ms=lambda:900_000)
    assert not result.ok and result.detail == "MANAGED_GRID_READER_ERROR"
    assert not root.exists()


@pytest.mark.parametrize("bad", [
    ["660000", "nan", "1", "1", "1", "10", "100"],
    ["660000", "inf", "1", "1", "1", "10", "100"],
    ["660000", "1", "0.9", "1.1", "1", "10", "100"],
    ["660000", "1", "1", "1", "1", "-1", "100"],
    ["660000", "1", "1", "1", "1", "10", "-1"],
    ["660001", "1", "1", "1", "1", "10", "100"],
    ["660000.0", "1", "1", "1", "1", "10", "100"],
    ["660000", "1", "1", "1", "1", "10"],
    ["660000", "1e9999", "1", "1", "1", "10", "100"],
    ["660000", "1", "1", "1", "1", True, "100"],
])
def test_malformed_managed_rows_denied_before_sqlite(tmp_path, bad):
    class BadReader:
        def fetch_klines(self, *args, **kwargs):
            return [bad, _row(720_000), _row(780_000)]
    root = tmp_path / "user-root"
    result = run_download_smoke(root, BadReader(), minutes=3, clock_ms=lambda:900_000)
    assert not result.ok and result.detail == "INVALID_MANAGED_GRID_ROWS"
    assert not root.exists()


def test_malformed_reader_container_denied(tmp_path):
    class InvalidReader:
        def fetch_klines(self, *args, **kwargs):
            return None
    root = tmp_path/"user-root"
    result = run_download_smoke(root, InvalidReader(), minutes=3, clock_ms=lambda:900_000)
    assert not result.ok and result.detail == "INVALID_MANAGED_GRID_ROWS"
    assert not root.exists()


@pytest.mark.parametrize("field,bad_value", [
    (1, "0"), (2, "0"), (3, "0"), (4, "0"),
    (5, "-0"), (5, "-0.000"), (6, "-0"),
    (6, "1e-10000"), (5, "1e-10000"), (1, "1e-10000"),
])
def test_g34_lossless_numeric_gate_rejects_before_sqlite(tmp_path, field, bad_value):
    root = tmp_path / "user-data"
    root.mkdir()
    sentinel = root / "market_download_smoke.sqlite3"
    sentinel.write_bytes(b"EXISTING-USER-DATA-UNCHANGED")
    bad = _row(660_000)
    bad[field] = bad_value
    class Reader:
        def fetch_klines(self, *args, **kwargs):
            return [bad, _row(720_000), _row(780_000)]
    result = run_download_smoke(root, Reader(), minutes=3, clock_ms=lambda:900_000)
    assert not result.ok
    assert result.detail == "INVALID_MANAGED_GRID_ROWS"
    assert sentinel.read_bytes() == b"EXISTING-USER-DATA-UNCHANGED"
    assert sorted(p.name for p in root.iterdir()) == [sentinel.name]


def test_g34_valid_zero_volume_and_turnover_retained(tmp_path):
    root = tmp_path / "user-data"
    class Reader:
        def fetch_klines(self, *args, **kwargs):
            rows = [_row(660_000), _row(720_000), _row(780_000)]
            rows[0][5:] = ["0", "0"]
            return rows
    result = run_download_smoke(root, Reader(), minutes=3, clock_ms=lambda:900_000)
    assert result.ok, result.detail
    assert result.count == 3
    assert not root.exists()


def _seed_real_sqlite_with_unique_history(path):
    """Create only a disposable fixture DB; persist every unique dataset."""
    from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle
    store = SQLiteMarketStore.open(path)
    try:
        assert store.upsert_candles([
            Candle("BTCUSDT", "1m", 60_000, 100, 101, 99, 100, 7, 700, True)
        ]).accepted == 1
        assert store.upsert_price_klines("mark_price", "BTCUSDT", [
            ["60000", "100", "101", "99", "100"]
        ]).accepted == 1
        assert store.upsert_price_klines("index_price", "BTCUSDT", [
            ["60000", "100", "101", "99", "100"]
        ]).accepted == 1
        assert store.upsert_price_klines("premium_index", "BTCUSDT", [
            ["60000", "0.01", "0.02", "0.00", "0.01"]
        ]).accepted == 1
        assert store.upsert_open_interest("BTCUSDT", [
            {"timestamp": "300000", "openInterest": "123.4"}
        ]).accepted == 1
        assert store.upsert_funding("BTCUSDT", [
            {"fundingRateTimestamp": "60000", "fundingRate": "0.0001"}
        ]).accepted == 1
        assert store.upsert_long_short_ratio("BTCUSDT", [
            {"timestamp": "300000", "buyRatio": "0.55", "sellRatio": "0.45"}
        ]).accepted == 1
        assert store.upsert_public_trade_aggregates("BTCUSDT", [
            {"open_time": 60000, "buy_volume": 3, "sell_volume": 2,
             "turnover": 500, "trade_count": 5, "vwap": 100,
             "max_trade": 2}
        ]).accepted == 1
    finally:
        store.close()


def _snapshot_sqlite_datasets(path):
    import sqlite3
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = (
            "candles", "mark_prices", "index_prices", "premium_index",
            "open_interest", "funding", "long_short_ratio",
            "public_trade_aggregates",
        )
        snapshot = {
            table: con.execute(
                f"SELECT * FROM {table} ORDER BY 1,2,3"
            ).fetchall() for table in tables
        }
        assert all(snapshot.values()), "every seeded unique dataset must remain populated"
        assert con.execute("PRAGMA quick_check").fetchone() == ("ok",)
        return snapshot
    finally:
        con.close()


@pytest.mark.parametrize("valid_rows", [True, False])
def test_g35_smoke_preserves_existing_unique_sqlite_datasets(tmp_path, valid_rows):
    # Real SQLite, not a byte sentinel. All files belong to pytest's temp dir.
    user_root = tmp_path / "preserved-data"
    user_root.mkdir()
    db = user_root / "market_download_smoke.sqlite3"
    _seed_real_sqlite_with_unique_history(db)
    baseline = _snapshot_sqlite_datasets(db)
    before_files = sorted(p.name for p in user_root.iterdir())

    class Reader:
        def fetch_klines(self, *args, **kwargs):
            rows = [_row(660_000), _row(720_000), _row(780_000)]
            if not valid_rows:
                rows[0][5] = "-0"
            return rows

    result = run_download_smoke(
        user_root, client=Reader(), minutes=3, clock_ms=lambda: 900_000
    )
    assert result.ok is valid_rows
    if not valid_rows:
        assert result.detail == "INVALID_MANAGED_GRID_ROWS"
    assert sorted(p.name for p in user_root.iterdir()) == before_files
    assert _snapshot_sqlite_datasets(db) == baseline
