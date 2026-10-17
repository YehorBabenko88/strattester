from dataclasses import replace

import pytest

from strattester.marketdata.sqlite_store import Candle, SQLiteMarketStore


@pytest.mark.parametrize("field,value", [
    ("open", float("inf")),
    ("high", float("inf")),
    ("low", float("-inf")),
    ("close", float("nan")),
    ("volume", float("nan")),
    ("turnover", float("inf")),
    ("turnover", float("nan")),
    ("open_time", 2**63),
    ("open_time", float("inf")),
    ("open_time", True),
    ("open_time", -1),
])
def test_invalid_candle_rejected_without_losing_valid_row(tmp_path, field, value):
    store = SQLiteMarketStore.open(tmp_path / "candles.sqlite3")
    try:
        valid = Candle("BTCUSDT", "1m", 1000, 1.0, 2.0, 1.0, 1.5, 1.0, 10.0)
        invalid = replace(valid, **{field: value})
        stats = store.upsert_candles([invalid, valid])
        assert stats.rejected == 1
        assert stats.accepted == 1
        assert list(store.iter_candles("BTCUSDT")) == [valid]
    finally:
        store.close()
