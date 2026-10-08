from types import SimpleNamespace

from strattester.marketdata.coverage import Coverage,TimeRange
from strattester.research.scientific_bootstrap import (
    build_symbol_science,
)


def candle(t,close=100.0):
    return SimpleNamespace(
        open_time=t,
        open=close,
        high=close+1,
        low=close-1,
        close=close,
        volume=1.0,
        turnover=100.0,
    )


class Store:
    def __init__(
        self,
        candles,
        trades=(),
        candle_gaps=(),
        trade_gaps=(),
    ):
        self._candles=list(candles)
        self._trades=list(trades)
        self._candle_gaps=tuple(candle_gaps)
        self._trade_gaps=tuple(trade_gaps)

    def iter_candles(
        self,
        symbol,
        timeframe,
        start_ms=None,
        end_ms=None,
    ):
        for row in self._candles:
            if (
                (start_ms is None or row.open_time>=start_ms)
                and
                (end_ms is None or row.open_time<=end_ms)
            ):
                yield row

    def iter_public_trade_aggregates(
        self,
        symbol,
        timeframe,
        start_ms=None,
        end_ms=None,
    ):
        for row in self._trades:
            t=int(row["t"])

            if (
                (start_ms is None or t>=start_ms)
                and
                (end_ms is None or t<=end_ms)
            ):
                yield row

    def coverage(
        self,
        symbol,
        dataset,
        timeframe,
        step_ms=60_000,
        start_ms=None,
        end_ms=None,
    ):
        if dataset=="candles":
            times=[
                x.open_time
                for x in self._candles
                if (
                    (start_ms is None or x.open_time>=start_ms)
                    and
                    (end_ms is None or x.open_time<=end_ms)
                )
            ]
            gaps=self._candle_gaps
        elif dataset=="public_trade_aggregates":
            times=[
                int(x["t"])
                for x in self._trades
                if (
                    (start_ms is None or int(x["t"])>=start_ms)
                    and
                    (end_ms is None or int(x["t"])<=end_ms)
                )
            ]
            gaps=self._trade_gaps
        else:
            times=[]
            gaps=()

        if not times:
            return Coverage(
                None,
                None,
                0,
                (),
            )

        return Coverage(
            min(times),
            max(times),
            len(times),
            gaps,
        )


def full_candles(count=41):
    return [
        candle(i*60_000,100+i)
        for i in range(count)
    ]


def full_trades(count=41):
    return [
        {
            "t":i*60_000,
            "buy_volume":2.0,
            "sell_volume":1.0,
        }
        for i in range(count)
    ]


def test_missing_trade_history_is_not_converted_to_zero_signal():
    bars=full_candles()

    s=Store(
        bars,
        trades=(),
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
        start_ms=0,
        end_ms=40*60_000,
    )

    assert result["status"]=="DEGRADED"

    assert (
        result["data_quality"]["candles"]
        =="COMPLETE_HISTORY"
    )

    assert (
        result["data_quality"]["public_trade_aggregates"]
        =="MISSING"
    )

    # Critical contract: absent dataset is unknown, not numeric zero.
    assert result["summary"]["mean_delta"] is None

    assert result["features"]["orderflow"]==[]
    assert result["features"]["scalp_events"]==[]


def test_gap_inside_required_candle_window_is_not_ready():
    bars=full_candles()

    s=Store(
        bars,
        candle_gaps=(
            TimeRange(
                10*60_000,
                10*60_000,
            ),
        ),
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
        start_ms=0,
        end_ms=40*60_000,
    )

    assert result["status"]=="INSUFFICIENT"

    assert (
        result["data_quality"]["candles"]
        =="PARTIAL_HISTORY"
    )

    assert "features" not in result


def test_short_history_is_insufficient_not_ready():
    bars=full_candles(20)

    s=Store(
        bars,
        trades=(),
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
        start_ms=0,
        end_ms=19*60_000,
    )

    assert result["status"]=="INSUFFICIENT"
    assert result["samples"]==20


def test_complete_required_datasets_are_ready():
    bars=full_candles()
    trades=full_trades()

    s=Store(
        bars,
        trades,
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
        start_ms=0,
        end_ms=40*60_000,
    )

    assert result["status"]=="READY"

    assert result["data_quality"]=={
        "candles":"COMPLETE_HISTORY",
        "public_trade_aggregates":"COMPLETE_HISTORY",
    }

    assert result["summary"]["mean_delta"]==1.0
    assert len(result["features"]["orderflow"])>0


def test_unbounded_bootstrap_never_claims_complete_history():
    bars=full_candles()
    trades=full_trades()

    s=Store(
        bars,
        trades,
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
    )

    # With no requested historical boundaries we can analyse the observed
    # range, but must not claim that it represents complete history.
    assert result["status"]=="DEGRADED"

    assert (
        result["data_quality"]["candles"]
        =="OBSERVED_RANGE_ONLY"
    )


def test_exactly_40_candles_fail_closed_without_graph_crash():
    bars=full_candles(40)

    s=Store(
        bars,
        trades=(),
    )

    result=build_symbol_science(
        s,
        "BTCUSDT",
        start_ms=0,
        end_ms=39*60_000,
    )

    assert result["status"]=="INSUFFICIENT"
    assert result["samples"]==40
    assert "41" in result["reason"]
    assert "features" not in result
