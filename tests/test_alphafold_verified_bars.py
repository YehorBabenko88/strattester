import sqlite3
import pytest

from strattester.alphafold_data_sync import SQLiteSource
from strattester.alphafold_series_integrity import DataIntegrityError
from strattester.alphafold_verified_bars import load_verified_regular_bars


def prepare(tmp_path, events):
    path = tmp_path / "bars.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE bars (
            instrument TEXT, timeframe TEXT, market_type TEXT,
            event_time INTEGER, ingestion_time INTEGER, watermark INTEGER,
            quality_status TEXT, eligible INTEGER)""")
        db.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?)", [
            ("BTCUSDT", "1m", "linear", t, t, t, "VERIFIED", 1)
            for t in events
        ])
    return SQLiteSource(path, "bars")


def read(source, **overrides):
    args = dict(instrument="BTCUSDT", timeframe="1m", market_type="linear",
                event_cutoff=120, knowledge_cutoff=120,
                accepted_quality="VERIFIED", interval=60,
                expected_start=0, max_rows=10)
    args.update(overrides)
    return load_verified_regular_bars(source, **args)


def test_integrated_valid_batch(tmp_path):
    assert len(read(prepare(tmp_path, [0, 60, 120]))) == 3


@pytest.mark.parametrize("events", [[0, 120], [0, 60, 60, 120], [60, 120]])
def test_integrated_incomplete_batch_rejected(tmp_path, events):
    with pytest.raises(DataIntegrityError):
        read(prepare(tmp_path, events))


def test_integrated_batch_limit_rejected(tmp_path):
    with pytest.raises(ValueError, match="max_rows"):
        read(prepare(tmp_path, [0, 60, 120]), max_rows=2)


def test_integrated_misaligned_window_rejected(tmp_path):
    with pytest.raises(ValueError, match="aligned"):
        read(prepare(tmp_path, [0, 60, 120]), event_cutoff=119)
