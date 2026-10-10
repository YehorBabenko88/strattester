from types import SimpleNamespace

import pytest

from strattester.research.result_persistence import (
    persist_report,
    persist_report_fenced,
)


class Store:
    def __init__(self):
        self.args=None

    def put(self,*args,**kwargs):
        self.args=(args,kwargs)


class FencedStore:
    def __init__(self,promote=True):
        self.stage_args=None
        self.promote_args=None
        self._promote=promote

    def stage(self,*args,**kwargs):
        self.stage_args=(args,kwargs)

    def promote(self,*args,**kwargs):
        self.promote_args=(args,kwargs)
        return self._promote


def objects():
    result=SimpleNamespace(
        strategy_id="A",
        strategy_version="1",
        fingerprint="fp",
    )

    report=SimpleNamespace(
        primary=SimpleNamespace(
            trades=2,
            net_pnl=3.0,
            fees=.2,
            win_rate=.5,
            profit_factor=2.0,
            max_drawdown=1.0,
            expectancy=1.5,
        )
    )

    return result,report


def test_persist_report_serializes_core_metrics():
    result,report=objects()
    s=Store()

    metrics=persist_report(
        s,
        "run-1",
        "BTCUSDT",
        result,
        report,
        coverage="COMPLETE_HISTORY",
    )

    args,_=s.args

    assert args[:4]==(
        "run-1",
        "BTCUSDT",
        "A",
        "1",
    )

    assert args[4]["trades"]==2
    assert args[4]["fingerprint"]=="fp"
    assert args[4]["coverage"]=="COMPLETE_HISTORY"
    assert metrics["coverage"]=="COMPLETE_HISTORY"


def test_persistence_cannot_invent_complete_history():
    result,report=objects()
    s=Store()

    with pytest.raises(TypeError):
        persist_report(
            s,
            "run-1",
            "BTCUSDT",
            result,
            report,
        )

    assert s.args is None


def test_partial_history_is_preserved_not_upgraded():
    result,report=objects()
    s=Store()

    metrics=persist_report(
        s,
        "run-1",
        "BTCUSDT",
        result,
        report,
        coverage="PARTIAL_HISTORY",
    )

    assert metrics["coverage"]=="PARTIAL_HISTORY"
    assert s.args[0][4]["coverage"]=="PARTIAL_HISTORY"


@pytest.mark.parametrize(
    "coverage",
    [
        "OBSERVED_RANGE_ONLY",
        "MISSING",
        "UNAVAILABLE",
        "INSUFFICIENT",
    ],
)
def test_noncomplete_quality_is_preserved(coverage):
    result,report=objects()
    s=Store()

    metrics=persist_report(
        s,
        "run-1",
        "BTCUSDT",
        result,
        report,
        coverage=coverage,
    )

    assert metrics["coverage"]==coverage


@pytest.mark.parametrize(
    "coverage",
    [
        "",
        "READY",
        "complete_history",
        "UNKNOWN",
        None,
    ],
)
def test_invalid_coverage_fails_before_store_write(
    coverage,
):
    result,report=objects()
    s=Store()

    with pytest.raises(ValueError):
        persist_report(
            s,
            "run-1",
            "BTCUSDT",
            result,
            report,
            coverage=coverage,
        )

    assert s.args is None


def test_fenced_persistence_preserves_partial_coverage():
    result,report=objects()
    s=FencedStore()

    metrics=persist_report_fenced(
        s,
        "stage-1",
        "run-1",
        "BTCUSDT",
        result,
        report,
        lambda:True,
        coverage="PARTIAL_HISTORY",
    )

    assert metrics["coverage"]=="PARTIAL_HISTORY"

    args,_=s.stage_args

    # stage(stage_id, run_id, symbol, strategy_id,
    #       strategy_version, metrics, ...)
    assert args[4]=="1"
    assert args[5]["coverage"]=="PARTIAL_HISTORY"


def test_fenced_persistence_requires_explicit_coverage():
    result,report=objects()
    s=FencedStore()

    with pytest.raises(TypeError):
        persist_report_fenced(
            s,
            "stage-1",
            "run-1",
            "BTCUSDT",
            result,
            report,
            lambda:True,
        )

    assert s.stage_args is None


def test_fenced_rejection_still_prevents_publication():
    result,report=objects()
    s=FencedStore(promote=False)

    with pytest.raises(
        RuntimeError,
        match="execution authority",
    ):
        persist_report_fenced(
            s,
            "stage-1",
            "run-1",
            "BTCUSDT",
            result,
            report,
            lambda:False,
            coverage="COMPLETE_HISTORY",
        )

    assert s.stage_args is not None
