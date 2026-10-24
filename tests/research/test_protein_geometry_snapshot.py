import sqlite3
import pytest
from strattester.research.protein_geometry_snapshot import readonly_candles


def test_snapshot_complete_bars_only(tmp_path):
    path = tmp_path / "market.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE candles(symbol TEXT,timeframe TEXT,open_time INTEGER,close REAL,complete INTEGER)")
    con.executemany("INSERT INTO candles VALUES(?,?,?,?,?)",
                    [("SOLUSDT", "1m", i * 60000, 100 + i, 1) for i in range(5)]
                    + [("SOLUSDT", "1m", 300000, 999, 0)])
    con.commit()
    con.close()
    with readonly_candles(path, "SOLUSDT") as rows:
        assert len(rows) == 5
        assert rows[-1] == (240000, 104)


def test_absent_database_not_created(tmp_path):
    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        with readonly_candles(path, "BTCUSDT"):
            pass
    assert not path.exists()
