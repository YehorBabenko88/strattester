import sqlite3

import pytest

from strattester.alphafold_data_sync import SQLiteSource, point_in_time_rows


def test_point_in_time_excludes_future_and_ineligible(tmp_path):
    path = tmp_path / "market.sqlite"
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE ticks (
        instrument TEXT, timeframe TEXT, market_type TEXT,
        event_time INTEGER, ingestion_time INTEGER, watermark INTEGER,
        quality_status TEXT, eligible INTEGER, price REAL)""")
    rows = [
        ("BTCUSDT", "1m", "linear", 100, 100, 100, "VERIFIED", 1, 1.0),
        ("BTCUSDT", "1m", "linear", 101, 150, 101, "VERIFIED", 1, 2.0),
        ("BTCUSDT", "1m", "linear", 90, 90, 90, "BAD", 1, 3.0),
        ("BTCUSDT", "1m", "linear", 95, 95, 95, "VERIFIED", 0, 4.0),
        ("BTCUSDT", "1m", "linear", 105, 105, 105, "VERIFIED", 1, 5.0),
    ]
    db.executemany("INSERT INTO ticks VALUES (?,?,?,?,?,?,?,?,?)", rows)
    db.commit()
    db.close()
    result = list(point_in_time_rows(
        SQLiteSource(path, "ticks"), instrument="BTCUSDT",
        timeframe="1m", market_type="linear", event_cutoff=101,
        knowledge_cutoff=110, accepted_quality="VERIFIED"))
    assert [row["price"] for row in result] == [1.0]


def test_read_only_rejects_missing_database(tmp_path):
    with pytest.raises(ValueError, match="existing regular"):
        list(point_in_time_rows(
            SQLiteSource(tmp_path / "missing.sqlite", "ticks"),
            instrument="BTCUSDT", timeframe="1m", market_type="linear",
            event_cutoff=1, knowledge_cutoff=1, accepted_quality="VERIFIED"))
    assert not (tmp_path / "missing.sqlite").exists()


def test_snapshot_is_stable_under_concurrent_writer(tmp_path):
    path = tmp_path / "market.sqlite"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE ticks (
        instrument TEXT, timeframe TEXT, market_type TEXT,
        event_time INTEGER, ingestion_time INTEGER, watermark INTEGER,
        quality_status TEXT, eligible INTEGER)""")
    record = ("BTCUSDT", "1m", "linear", 1, 1, 1, "VERIFIED", 1)
    db.execute("INSERT INTO ticks VALUES (?,?,?,?,?,?,?,?)", record)
    db.commit()
    source = SQLiteSource(path, "ticks")
    reader = point_in_time_rows(
        source, instrument="BTCUSDT", timeframe="1m", market_type="linear",
        event_cutoff=10, knowledge_cutoff=10, accepted_quality="VERIFIED")
    assert next(reader)["event_time"] == 1
    db.execute("INSERT INTO ticks VALUES (?,?,?,?,?,?,?,?)",
               ("BTCUSDT", "1m", "linear", 2, 2, 2, "VERIFIED", 1))
    db.commit()
    assert list(reader) == []
    reader.close()
    assert len(list(point_in_time_rows(
        source, instrument="BTCUSDT", timeframe="1m", market_type="linear",
        event_cutoff=10, knowledge_cutoff=10, accepted_quality="VERIFIED"))) == 2
    db.close()


def test_reject_symlink_source(tmp_path):
    actual = tmp_path / "real.sqlite"
    sqlite3.connect(actual).close()
    link = tmp_path / "link.sqlite"
    try:
        link.symlink_to(actual)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="non-symlink"):
        list(point_in_time_rows(
            SQLiteSource(link, "ticks"), instrument="BTCUSDT",
            timeframe="1m", market_type="linear", event_cutoff=1,
            knowledge_cutoff=1, accepted_quality="VERIFIED"))


def test_bounded_reader_rejects_partial_batch(tmp_path):
    from strattester.alphafold_data_sync import bounded_point_in_time_rows
    path = tmp_path / "data.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE ticks (
            instrument TEXT, timeframe TEXT, market_type TEXT,
            event_time INTEGER, ingestion_time INTEGER, watermark INTEGER,
            quality_status TEXT, eligible INTEGER)""")
        db.executemany("INSERT INTO ticks VALUES (?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "1m", "linear", i, i, i, "VERIFIED", 1)
            for i in range(3)
        ])
    filters = dict(instrument="BTCUSDT", timeframe="1m",
                   market_type="linear", event_cutoff=10,
                   knowledge_cutoff=10, accepted_quality="VERIFIED")
    with pytest.raises(ValueError, match="exceeds max_rows"):
        bounded_point_in_time_rows(SQLiteSource(path, "ticks"),
                                   max_rows=2, **filters)
    assert len(bounded_point_in_time_rows(
        SQLiteSource(path, "ticks"), max_rows=3, **filters)) == 3
    with pytest.raises(ValueError, match="positive integer"):
        bounded_point_in_time_rows(SQLiteSource(path, "ticks"),
                                   max_rows=0, **filters)
