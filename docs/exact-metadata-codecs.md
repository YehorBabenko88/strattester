# Exact metadata and UTC representation codecs

Base Data100 b3d9bf390e736b276ec5994aaa136b117d3ef714, not experimental schema3. Actual repro initially13failed/3passed: tickSize0.10000000000000000001 became float0.1; milliseconds10000000000001 became UTC2286-11-20T17:46:40.000999 instead of.001000; Windows fromtimestamp refused valid year9999.

Discovery now reuses the existing canonical public trade exact scalar parser and decimal_text formatter. Each item is schema market_data.linear-instrument.v1, tick_size is a CANONICAL_EXACT_DECIMAL string; no float compatibility shim. Numeric values are exact, original lexical trailing zeros/exponent spelling are not asserted wire bytes. The existing paged HTTP reader remains the sole transport. No source authenticity, complete historical universe or live execution grant follows.

Existing FootprintBuilder accepts Decimal(str(tick)); instrument-state API already demands a SQL Decimal and returns text. No active linear_symbols caller was found in selected canonical Data/Root installer/source-admission source trees; retained original Grid callers are NOT migrated/active and cannot be resumed by aliasing this package. Future SQL writers must construct Decimal from the string without float. No Root/Terminan source edit was needed by this change.

Timestamp codec accepts only strict nonboolean integer or canonical bounded ASCII-decimal text0..253402300799999. UTC conversion uses EPOCH+timedelta(milliseconds=intms); inverse requires aware UTC and whole milliseconds and uses exact stdlib timedelta divmod. No float seconds/platform timestamp. Backfill cursor inverse and UTC archive-day boundaries reuse the same codec. DateTime objects are representation data, not a new quantitative algorithm.

store_kline_page validates the full bounded page before ANY pool/transaction await and builds an immutable tuple of exact Decimal/UTC values. The single canonical scalar parser permits zero only for volume/turnover; default Trade price/quantity remains strictly positive. Existing Math candle_ohlcv_valid owns OHLCV numeric integrity; no local financial/domain formula was copied. Provider decimal strings never pass through float. We found no prior Python float conversion of OHLCV prices/volumes themselves; actual PostgreSQL/driver stored fidelity remains untested.

575 source cases passed before the final hostile-context regression/artifact build; final receipts supersede this intermediate count. Tests use synthetic page/fake pool and actual SDK only; no provider/DB/native operation.

Final scoped source verification:576 PASS with reviewed Math d88, including hostile Decimal precision2/all traps/Emax2/Emin-2 and caller flags unchanged. Artifact and independent acceptance are separate receipts. No actual DB/DDL/source migration occurred.
