SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    turnover REAL,
    complete INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(symbol, timeframe, open_time)
);
CREATE INDEX IF NOT EXISTS idx_candles_lookup
ON candles(symbol, timeframe, open_time);
"""
