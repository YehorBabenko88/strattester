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


class ProbeStrategy:
    init_calls=0
    run_calls=0

    def __init__(self):
        type(self).init_calls += 1

    def run_context(self,context,checkpoint=None):
        type(self).run_calls += 1
        return {
            "candles": sum(
                1 for _ in context.candles("1m")
            ),
        }


def reset_probe():
    ProbeStrategy.init_calls=0
    ProbeStrategy.run_calls=0


def candles_1m(end_ms):
    return [
        Candle(
            "BTCUSDT",
            "1m",
            t,
            100.0,
            101.0,
            99.0,
            100.0,
            1.0,
        )
        for t in range(
            0,
            end_ms + 1,
            60_000,
        )
    ]


def definition(dataset,timeframe,required=True):
    return StrategyDefinition(
        f"aux-gate-{dataset}",
        "1",
        (
            DataRequirement(
                "candles",
                ("1m",),
                required=True,
            ),
            DataRequirement(
                dataset,
                (timeframe,),
                required=required,
            ),
        ),
        ProbeStrategy,
    )


def write_aux(store,dataset,timeframe,times):
    if dataset=="mark_price":
        store.upsert_price_klines(
            "mark_price",
            "BTCUSDT",
            [
                [
                    str(t),
                    "100",
                    "101",
                    "99",
                    "100",
                ]
                for t in times
            ],
            timeframe,
        )
        return

    if dataset=="open_interest":
        store.upsert_open_interest(
            "BTCUSDT",
            [
                {
                    "timestamp":str(t),
                    "openInterest":"123.45",
                }
                for t in times
            ],
            timeframe,
        )
        return

    if dataset=="funding":
        store.upsert_funding(
            "BTCUSDT",
            [
                {
                    "fundingRateTimestamp":str(t),
                    "fundingRate":"0.0001",
                }
                for t in times
            ],
        )
        return

    if dataset=="long_short_ratio":
        store.upsert_long_short_ratio(
            "BTCUSDT",
            [
                {
                    "timestamp":str(t),
                    "buyRatio":"0.55",
                    "sellRatio":"0.45",
                }
                for t in times
            ],
            timeframe,
        )
        return

    if dataset=="public_trade_aggregates":
        store.upsert_public_trade_aggregates(
            "BTCUSDT",
            [
                {
                    "open_time":t,
                    "buy_volume":10.0,
                    "sell_volume":9.0,
                    "turnover":1900.0,
                    "trade_count":10,
                    "vwap":100.0,
                    "max_trade":2.0,
                }
                for t in times
            ],
            timeframe,
        )
        return

    raise AssertionError(
        f"unsupported test dataset: {dataset}"
    )


CASES = [
    (
        "mark_price",
        "1m",
        60_000,
    ),
    (
        "open_interest",
        "5m",
        300_000,
    ),
    (
        "funding",
        "8h",
        28_800_000,
    ),
    (
        "long_short_ratio",
        "5m",
        300_000,
    ),
    (
        "public_trade_aggregates",
        "1m",
        60_000,
    ),
]


@pytest.mark.parametrize(
    "dataset,timeframe,step",
    CASES,
)
def test_missing_required_aux_dataset_blocks_before_strategy(
    tmp_path,
    dataset,
    timeframe,
    step,
):
    end_ms=step*4

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles(
            candles_1m(end_ms)
        )

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(
                    dataset,
                    timeframe,
                    required=True,
                ),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=end_ms,
            )

        assert ProbeStrategy.init_calls==0
        assert ProbeStrategy.run_calls==0

    finally:
        store.close()


@pytest.mark.parametrize(
    "dataset,timeframe,step",
    CASES,
)
def test_internal_gap_in_required_aux_dataset_blocks_execution(
    tmp_path,
    dataset,
    timeframe,
    step,
):
    end_ms=step*4

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles(
            candles_1m(end_ms)
        )

        times=[
            0,
            step,
            # 2*step deliberately missing.
            3*step,
            4*step,
        ]

        write_aux(
            store,
            dataset,
            timeframe,
            times,
        )

        cov=store.coverage(
            "BTCUSDT",
            dataset,
            timeframe,
            step_ms=step,
            start_ms=0,
            end_ms=end_ms,
        )

        assert cov.count==4
        assert cov.gaps

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(
                    dataset,
                    timeframe,
                    required=True,
                ),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=end_ms,
            )

        assert ProbeStrategy.init_calls==0
        assert ProbeStrategy.run_calls==0

    finally:
        store.close()


@pytest.mark.parametrize(
    "dataset,timeframe,step",
    CASES,
)
def test_repairing_aux_gap_makes_required_dataset_ready(
    tmp_path,
    dataset,
    timeframe,
    step,
):
    end_ms=step*4

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles(
            candles_1m(end_ms)
        )

        write_aux(
            store,
            dataset,
            timeframe,
            [
                0,
                step,
                3*step,
                4*step,
            ],
        )

        reset_probe()

        with pytest.raises(
            RuntimeError,
            match="strategy requirements are not ready",
        ):
            execute_strategy(
                definition(
                    dataset,
                    timeframe,
                ),
                store,
                "BTCUSDT",
                start_ms=0,
                end_ms=end_ms,
            )

        assert ProbeStrategy.init_calls==0
        assert ProbeStrategy.run_calls==0

        # Restore only the missing observation.
        write_aux(
            store,
            dataset,
            timeframe,
            [2*step],
        )

        cov=store.coverage(
            "BTCUSDT",
            dataset,
            timeframe,
            step_ms=step,
            start_ms=0,
            end_ms=end_ms,
        )

        assert cov.count==5
        assert cov.gaps==()

        result=execute_strategy(
            definition(
                dataset,
                timeframe,
            ),
            store,
            "BTCUSDT",
            start_ms=0,
            end_ms=end_ms,
        )

        assert result.output["candles"]>0
        assert ProbeStrategy.init_calls==1
        assert ProbeStrategy.run_calls==1

    finally:
        store.close()


@pytest.mark.parametrize(
    "dataset,timeframe,step",
    CASES,
)
def test_missing_optional_aux_dataset_does_not_block_execution(
    tmp_path,
    dataset,
    timeframe,
    step,
):
    end_ms=step*4

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        store.upsert_candles(
            candles_1m(end_ms)
        )

        reset_probe()

        result=execute_strategy(
            definition(
                dataset,
                timeframe,
                required=False,
            ),
            store,
            "BTCUSDT",
            start_ms=0,
            end_ms=end_ms,
        )

        assert result.output["candles"]>0
        assert ProbeStrategy.init_calls==1
        assert ProbeStrategy.run_calls==1

        # Crucial distinction:
        # optional means "strategy may run without it".
        # It does NOT mean "missing data equals numeric zero".
        cov=store.coverage(
            "BTCUSDT",
            dataset,
            timeframe,
            step_ms=step,
            start_ms=0,
            end_ms=end_ms,
        )

        assert cov.count==0
        assert cov.earliest is None
        assert cov.latest is None

    finally:
        store.close()


def test_historical_public_trades_are_not_fabricated_by_sync(
    tmp_path,
):
    """
    The local store can contain archive-derived trade aggregates,
    but the normal REST sync engine must not pretend that recent
    REST trades are complete historical public-trade coverage.
    """
    from strattester.marketdata.sync_engine import (
        DataRequirement as SyncRequirement,
        SyncEngine,
        SyncState,
    )

    class Client:
        pass

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        engine=SyncEngine(
            store,
            Client(),
        )

        result=engine.sync_requirement(
            SyncRequirement(
                "BTCUSDT",
                "public_trade_aggregates",
                "1m",
                0,
                240_000,
            )
        )

        assert result.state is SyncState.REPAIR_REQUIRED
        assert "archive" in result.message.lower()

        cov=store.coverage(
            "BTCUSDT",
            "public_trade_aggregates",
            "1m",
            step_ms=60_000,
            start_ms=0,
            end_ms=240_000,
        )

        assert cov.count==0

    finally:
        store.close()
