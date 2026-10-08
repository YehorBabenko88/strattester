import pytest

from strattester.engine.executor import _coverage_ready
from strattester.marketdata.sqlite_store import (
    Candle,
    SQLiteMarketStore,
)
from strattester.marketdata.timeframes import (
    aligned_window,
)
from strattester.research.runner import (
    LifecycleWindowError,
    ResearchRunner,
)
from strattester.strategies.base import (
    DataRequirement,
    StrategyDefinition,
)


class NoRun:
    def run_context(self,context,checkpoint=None):
        return "OK"


def definition(*requirements):
    return StrategyDefinition(
        "cadence-test",
        "1",
        tuple(requirements),
        NoRun,
    )


def candle(symbol,ts):
    return Candle(
        symbol,
        "1m",
        ts,
        1.0,
        1.1,
        0.9,
        1.0,
        1.0,
        1.0,
        True,
    )


def test_required_5m_window_counts_only_real_grid_points(tmp_path):
    store=SQLiteMarketStore.open(
        tmp_path / "m.db"
    )

    # Store one OI observation at the only actual 5m grid point
    # inside 60_000..360_000.
    store.upsert_open_interest(
        "XUSDT",
        [
            {
                "timestamp":"300000",
                "openInterest":"10",
            }
        ],
        "5m",
    )

    assert _coverage_ready(
        store,
        "XUSDT",
        "open_interest",
        "5m",
        60_000,
        360_000,
    )

    store.close()


def test_required_dataset_with_no_complete_grid_point_fails_closed(
    tmp_path,
):
    store=SQLiteMarketStore.open(
        tmp_path / "m.db"
    )

    assert not _coverage_ready(
        store,
        "XUSDT",
        "open_interest",
        "5m",
        60_000,
        179_999,
    )

    store.close()


def test_runner_does_not_request_before_resume_grid_boundary():
    class Client:
        def __init__(self):
            self.calls=[]

        def fetch_open_interest(
            self,
            symbol,
            start,
            end,
            interval,
        ):
            self.calls.append(
                (
                    symbol,
                    start,
                    end,
                    interval,
                )
            )

            return [
                {
                    "timestamp":str(start),
                    "openInterest":"10",
                },
                {
                    "timestamp":str(end),
                    "openInterest":"11",
                },
            ] if start!=end else [
                {
                    "timestamp":str(start),
                    "openInterest":"10",
                }
            ]

    class Impl:
        def run_context(
            self,
            context,
            checkpoint=None,
        ):
            return "OK"

    # We only call _sync_definition here so executor does not require
    # candles unrelated to this unit test.
    store=SQLiteMarketStore.open(":memory:")
    client=Client()

    runner=ResearchRunner(
        store,
        client,
        clock_ms=lambda:10_000_000,
    )

    d=StrategyDefinition(
        "oi",
        "1",
        (
            DataRequirement(
                "open_interest",
                ("5m",),
            ),
        ),
        Impl,
    )

    runner._sync_definition(
        d,
        "XUSDT",
        240_001,
        600_000,
    )

    assert client.calls==[
        (
            "XUSDT",
            300_000,
            600_000,
            "5min",
        )
    ]

    store.close()


def test_runner_required_5m_dataset_without_observation_window_rejected(
    tmp_path,
):
    class Client:
        def fetch_open_interest(self,*args,**kwargs):
            raise AssertionError(
                "network must not be called"
            )

    store=SQLiteMarketStore.open(
        tmp_path / "m.db"
    )

    runner=ResearchRunner(
        store,
        Client(),
    )

    d=definition(
        DataRequirement(
            "open_interest",
            ("5m",),
        )
    )

    with pytest.raises(
        LifecycleWindowError,
        match="no complete 5m observation",
    ):
        runner._sync_definition(
            d,
            "XUSDT",
            60_000,
            179_999,
        )

    store.close()


def test_optional_dataset_without_grid_point_is_skipped(
    tmp_path,
):
    class Client:
        def fetch_open_interest(self,*args,**kwargs):
            raise AssertionError(
                "optional dataset must be skipped"
            )

    store=SQLiteMarketStore.open(
        tmp_path / "m.db"
    )

    runner=ResearchRunner(
        store,
        Client(),
    )

    d=definition(
        DataRequirement(
            "open_interest",
            ("5m",),
            required=False,
        )
    )

    assert runner._sync_definition(
        d,
        "XUSDT",
        60_000,
        179_999,
    ) == ()

    store.close()
