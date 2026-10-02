SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candles (
 symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,
 open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,
 volume REAL NOT NULL,turnover REAL,complete INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(symbol,timeframe,open_time));
CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol,timeframe,open_time);
CREATE TABLE IF NOT EXISTS mark_prices (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,complete INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(symbol,timeframe,open_time));
CREATE TABLE IF NOT EXISTS index_prices (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,complete INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(symbol,timeframe,open_time));
CREATE TABLE IF NOT EXISTS premium_index (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,complete INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(symbol,timeframe,open_time));
CREATE TABLE IF NOT EXISTS open_interest (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,value REAL NOT NULL,complete INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(symbol,timeframe,open_time));
CREATE TABLE IF NOT EXISTS funding (symbol TEXT NOT NULL,funding_time INTEGER NOT NULL,rate REAL NOT NULL,PRIMARY KEY(symbol,funding_time));
CREATE TABLE IF NOT EXISTS long_short_ratio (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,buy_ratio REAL,sell_ratio REAL,long_short_ratio REAL,PRIMARY KEY(symbol,timeframe,open_time));
CREATE TABLE IF NOT EXISTS public_trade_aggregates (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,open_time INTEGER NOT NULL,buy_volume REAL NOT NULL DEFAULT 0,sell_volume REAL NOT NULL DEFAULT 0,turnover REAL NOT NULL DEFAULT 0,trade_count INTEGER NOT NULL DEFAULT 0,vwap REAL,max_trade REAL,PRIMARY KEY(symbol,timeframe,open_time));
"""