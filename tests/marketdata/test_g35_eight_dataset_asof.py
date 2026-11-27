"""G owner: eight retained SQLite families, field/as-of/closed-row contract.

Disposable SQLite only. This is NOT canonical Grid parity or live source proof.
Keep the legacy history until separately attested Grid/Math/Terminan parity.
"""
import sqlite3

import pytest

from strattester.marketdata.sqlite_store import Candle, SQLiteMarketStore


def _seed_all_eight(store):
    candle = lambda t: Candle("BTCUSDT", "1m", t, 100, 102, 99, 101, 5, 505, True)
    assert store.upsert_candles([candle(60_000), candle(120_000)]).accepted == 2
    for kind in ("mark_price", "index_price", "premium_index"):
        rows = ([str(t), "0.01", "0.02", "0.00", "0.01"] if kind == "premium_index"
                else [str(t), "100", "102", "99", "101"]
                for t in (60_000, 120_000))
        assert store.upsert_price_klines(kind, "BTCUSDT", list(rows)).accepted == 2
    assert store.upsert_open_interest("BTCUSDT", [
        {"timestamp": "300000", "openInterest": "123.4"},
        {"timestamp": "600000", "openInterest": "125.6"},
    ]).accepted == 2
    assert store.upsert_funding("BTCUSDT", [
        {"fundingRateTimestamp": "60000", "fundingRate": "0.0001"},
        {"fundingRateTimestamp": "120000", "fundingRate": "0.0002"},
    ]).accepted == 2
    assert store.upsert_long_short_ratio("BTCUSDT", [
        {"timestamp": "300000", "buyRatio": "0.55", "sellRatio": "0.45"},
        {"timestamp": "600000", "buyRatio": "0.60", "sellRatio": "0.40"},
    ]).accepted == 2
    assert store.upsert_public_trade_aggregates("BTCUSDT", [
        {"open_time": 60000, "buy_volume": 3, "sell_volume": 2,
         "turnover": 505, "trade_count": 5, "vwap": 101, "max_trade": 2},
        {"open_time": 120000, "buy_volume": 7, "sell_volume": 4,
         "turnover": 1111, "trade_count": 11, "vwap": 101, "max_trade": 3},
    ]).accepted == 2


@pytest.mark.parametrize("dataset,timeframe,step,cutoff", [
    ("candles", "1m", 60_000, 60_000),
    ("mark_price", "1m", 60_000, 60_000),
    ("index_price", "1m", 60_000, 60_000),
    ("premium_index", "1m", 60_000, 60_000),
    ("open_interest", "5m", 300_000, 300_000),
    ("funding", "funding", 60_000, 60_000),
    ("long_short_ratio", "5m", 300_000, 300_000),
    ("public_trade_aggregates", "1m", 60_000, 60_000),
])
def test_g35_eight_dataset_asof_survives_reopen(tmp_path, dataset, timeframe, step, cutoff):
    path = tmp_path / "g35-unique-history.sqlite3"
    store = SQLiteMarketStore.open(path)
    _seed_all_eight(store)
    assert store.coverage(
        "BTCUSDT", dataset, timeframe, step, end_ms=cutoff
    ).count == 1
    assert store.coverage(
        "BTCUSDT", dataset, timeframe, step, end_ms=cutoff + step
    ).count == 2
    store.close()

    reopened = SQLiteMarketStore.open(path)
    try:
        before = reopened.coverage(
            "BTCUSDT", dataset, timeframe, step, end_ms=cutoff
        )
        assert before.count == 1 and before.earliest == cutoff
        assert reopened.coverage(
            "BTCUSDT", dataset, timeframe, step, end_ms=cutoff + step
        ).count == 2
        assert reopened.integrity_check()
    finally:
        reopened.close()


@pytest.mark.parametrize("dataset,table,timeframe,ts", [
    ("candles", "candles", "1m", 120_000),
    ("mark_price", "mark_prices", "1m", 120_000),
    ("index_price", "index_prices", "1m", 120_000),
    ("premium_index", "premium_index", "1m", 120_000),
    ("open_interest", "open_interest", "5m", 600_000),
])
def test_g35_incomplete_rows_not_reported_as_closed_coverage(
    tmp_path, dataset, table, timeframe, ts
):
    path = tmp_path / "incomplete.sqlite3"
    store = SQLiteMarketStore.open(path)
    _seed_all_eight(store)
    try:
        store.connection.execute(
            f"UPDATE {table} SET complete=0 WHERE symbol=? AND open_time=?",
            ("BTCUSDT", ts),
        )
        store.connection.commit()
        step = 300_000 if dataset == "open_interest" else 60_000
        cov = store.coverage("BTCUSDT", dataset, timeframe, step)
        assert cov.count == 1 and cov.latest == ts - step
        assert store.integrity_check()
    finally:
        store.close()


def test_g35_public_trade_delta_turnover_asof_and_unique_fields(tmp_path):
    store = SQLiteMarketStore.open(tmp_path / "trade-history.sqlite3")
    _seed_all_eight(store)
    try:
        prior = list(store.iter_public_trade_aggregates(
            "BTCUSDT", start_ms=60_000, end_ms=60_000
        ))
        assert len(prior) == 1
        assert prior[0]["buy_volume"] == 3
        assert prior[0]["sell_volume"] == 2
        assert prior[0]["delta"] == 1
        assert prior[0]["turnover"] == 505
        assert prior[0]["trade_count"] == 5
        assert prior[0]["vwap"] == 101
        assert prior[0]["max_trade"] == 2
        later = list(store.iter_public_trade_aggregates(
            "BTCUSDT", start_ms=120_000, end_ms=120_000
        ))
        assert len(later) == 1 and later[0]["delta"] == 3
        assert later[0]["turnover"] == 1111
    finally:
        store.close()


@pytest.mark.parametrize("dataset,table,rows", [
    ("open_interest", "open_interest", [
        {"timestamp": "900000", "openInterest": "inf"},
    ]),
    ("funding", "funding", [
        {"fundingRateTimestamp": "180000", "fundingRate": "nan"},
    ]),
    ("long_short_ratio", "long_short_ratio", [
        {"timestamp": "900000", "buyRatio": "nan", "sellRatio": "0.5"},
    ]),
    ("long_short_ratio", "long_short_ratio", [
        {"timestamp": "900000", "buyRatio": "1e308", "sellRatio": "1e-308"},
    ]),
    ("public_trade_aggregates", "public_trade_aggregates", [
        {"open_time": 180000, "buy_volume": 3, "sell_volume": 2,
         "turnover": 500, "trade_count": 5, "vwap": "nan", "max_trade": 2},
    ]),
    ("public_trade_aggregates", "public_trade_aggregates", [
        {"open_time": 180000, "buy_volume": 3, "sell_volume": 2,
         "turnover": 500, "trade_count": 5, "vwap": 100, "max_trade": "inf"},
    ]),
    ("public_trade_aggregates", "public_trade_aggregates", [
        {"open_time": 180000, "buy_volume": 3, "sell_volume": 2,
         "turnover": "inf", "trade_count": 5, "vwap": 100, "max_trade": 2},
    ]),
])
def test_g35_nonfinite_unique_history_rejected_without_data_loss(
    tmp_path, dataset, table, rows
):
    store = SQLiteMarketStore.open(tmp_path / "nonfinite-rejection.sqlite3")
    _seed_all_eight(store)
    try:
        before = store.connection.execute(
            f"SELECT * FROM {table} ORDER BY 1,2"
        ).fetchall()
        writers = {
            "open_interest": store.upsert_open_interest,
            "funding": store.upsert_funding,
            "long_short_ratio": store.upsert_long_short_ratio,
            "public_trade_aggregates": store.upsert_public_trade_aggregates,
        }
        stats = writers[dataset]("BTCUSDT", rows)
        assert stats.accepted == 0 and stats.rejected == 1
        assert store.connection.execute(
            f"SELECT * FROM {table} ORDER BY 1,2"
        ).fetchall() == before
        assert store.integrity_check()
    finally:
        store.close()
