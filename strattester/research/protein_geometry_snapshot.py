"""Read-only SQLite candle snapshot, independent of write-capable store initialization."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


@contextmanager
def readonly_candles(db_path, symbol, timeframe="1m", start_ms=None, end_ms=None):
    path = Path(db_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("database path is not a file")
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=15)
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        cols = {r[1] for r in con.execute("PRAGMA table_info(candles)")}
        legacy = "ts" in cols and "open_time" not in cols
        if legacy and timeframe != "1m":
            raise ValueError("legacy candles support 1m only")
        timecol = "ts" if legacy else "open_time"
        where = ["symbol=?"]
        params = [symbol]
        if not legacy:
            where.extend(["timeframe=?", "complete=1"])
            params.append(timeframe)
        if start_ms is not None:
            where.append(f"{timecol}>=?")
            params.append(int(start_ms))
        if end_ms is not None:
            where.append(f"{timecol}<=?")
            params.append(int(end_ms))
        cursor = con.execute(
            f"SELECT {timecol},close FROM candles WHERE {' AND '.join(where)} ORDER BY {timecol}",
            tuple(params))
        yield tuple((int(t), float(c)) for t, c in cursor)
    finally:
        con.rollback()
        con.close()
