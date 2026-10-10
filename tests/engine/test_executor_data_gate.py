import pytest

from strattester.engine.executor import execute_strategy
from strattester.marketdata.sqlite_store import (
    SQLiteMarketStore,
    Candle,
)
from strattester.strategies.base import (
    StrategyDefinition,
    DataRequirement,
)


class GuardedStrategy:
    init_calls=0
    run_calls=0

    def __init__(self):
        type(self).init_calls += 1

    def run(self,candles,checkpoint=None):
        type(self).run_calls += 1
        return len(list(candles))


def definition():
    return StrategyDefinition(
        "data-gate-probe",
        "1",
        (
            DataRequirement(
                "candles",
                ("1m",),
                required=True,
            ),
        ),
        GuardedStrategy,
    )


def candle(t):
    return Candle(
        "BTCUSDT",
        "1m",
        t,
        100.0,
        101.0,
        99.0,
        100.0,
        1.0,
    )


def reset_probe():
    GuardedStrategy.init_calls=0
    GuardedStrategy.run_calls=0


def test_internal_required_gap_blocks_before_strategy_instantiation(
    tmp_path,
):
    """
    Required history:
        0, 60s, 120s, 180s, 240s

    Stored history deliberately omits 120s.

    Even though rows exist before and after the missing candle,
    execution must fail before strategy construction/run.
    """
    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles([
            candle(0),
            candle(60_000),

            # 120_000 deliberately missing.

            candle(180_000),
            candle(240_000),
        ])

        coverage=store.coverage(
            "BTCUSDT",
            "candles",
            "1m",
            step_ms=60_000,
            start_ms=0,
            end_ms=240_000,
        )

        assert coverage.count==4
        assert coverage.gaps

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=240_000,
            )

        # Critical fail-closed guarantee:
        # not only no trade, but no strategy execution whatsoever.
        assert GuardedStrategy.init_calls==0
        assert GuardedStrategy.run_calls==0

    finally:
        store.close()


def test_repaired_required_gap_allows_execution(
    tmp_path,
):
    """
    Once exactly the missing candle is restored,
    the same requested window becomes executable.
    """
    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles([
            candle(0),
            candle(60_000),
            candle(180_000),
            candle(240_000),
        ])

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=240_000,
            )

        assert GuardedStrategy.init_calls==0
        assert GuardedStrategy.run_calls==0

        # Repair only the missing minute.
        store.upsert_candles([
            candle(120_000),
        ])

        coverage=store.coverage(
            "BTCUSDT",
            "candles",
            "1m",
            step_ms=60_000,
            start_ms=0,
            end_ms=240_000,
        )

        assert coverage.count==5
        assert coverage.gaps==()

        result=execute_strategy(
            definition(),
            store,
            "BTCUSDT",
            start_ms=0,
            end_ms=240_000,
        )

        assert result.output==5
        assert GuardedStrategy.init_calls==1
        assert GuardedStrategy.run_calls==1

    finally:
        store.close()


def test_rows_outside_requested_window_cannot_hide_internal_gap(
    tmp_path,
):
    """
    A large amount of valid history outside the research interval
    must not compensate for a missing candle inside the interval.
    """
    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles([
            candle(-120_000),
            candle(-60_000),
            candle(0),
            candle(60_000),

            # Required 120_000 is missing.

            candle(180_000),
            candle(240_000),
            candle(300_000),
            candle(360_000),
        ])

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=240_000,
            )

        assert GuardedStrategy.init_calls==0
        assert GuardedStrategy.run_calls==0

    finally:
        store.close()
