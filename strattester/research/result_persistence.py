from __future__ import annotations

from dataclasses import asdict,is_dataclass


_ALLOWED_COVERAGE=frozenset({
    "COMPLETE_HISTORY",
    "PARTIAL_HISTORY",
    "OBSERVED_RANGE_ONLY",
    "MISSING",
    "UNAVAILABLE",
    "INSUFFICIENT",
})


def _metrics(m):
    if is_dataclass(m):
        d=asdict(m)
    else:
        keys=(
            "trades",
            "wins",
            "losses",
            "win_rate",
            "gross_pnl",
            "net_pnl",
            "fees",
            "expectancy",
            "profit_factor",
            "max_drawdown",
            "avg_mae",
            "avg_mfe",
            "avg_r_multiple",
            "avg_holding_ms",
            "max_consecutive_losses",
        )

        d={
            k:getattr(m,k)
            for k in keys
            if hasattr(m,k)
        }

    return d


def _validated_coverage(coverage):
    if not isinstance(coverage,str):
        raise ValueError(
            "coverage must be supplied explicitly"
        )

    coverage=coverage.strip()

    if coverage not in _ALLOWED_COVERAGE:
        raise ValueError(
            f"unsupported coverage classification: {coverage!r}"
        )

    return coverage


def _persistent_metrics(
    strategy_result,
    report,
    *,
    coverage,
):
    coverage=_validated_coverage(
        coverage
    )

    metrics=_metrics(
        report.primary
    )

    metrics["fingerprint"]=(
        strategy_result.fingerprint
    )

    # Persistence records the classification proved by the caller.
    # It must never manufacture COMPLETE_HISTORY itself.
    metrics["coverage"]=coverage

    return metrics


def persist_report(
    store,
    run_id,
    symbol,
    strategy_result,
    report,
    *,
    coverage,
):
    metrics=_persistent_metrics(
        strategy_result,
        report,
        coverage=coverage,
    )

    store.put(
        run_id,
        symbol,
        strategy_result.strategy_id,
        strategy_result.strategy_version,
        metrics,
    )

    return metrics


def persist_report_fenced(
    store,
    stage_id,
    run_id,
    symbol,
    strategy_result,
    report,
    lease_validator,
    job_id=None,
    lease_token=0,
    node_generation=0,
    *,
    coverage,
):
    """
    Persist scientific output without allowing a stale worker to publish it.

    Coverage is mandatory and must already have been established by the
    data-quality layer. Persistence is not allowed to upgrade data quality.
    """
    metrics=_persistent_metrics(
        strategy_result,
        report,
        coverage=coverage,
    )

    store.stage(
        stage_id,
        run_id,
        symbol,
        strategy_result.strategy_id,
        strategy_result.strategy_version,
        metrics,
        job_id=job_id,
        lease_token=lease_token,
        node_generation=node_generation,
    )

    if not store.promote(
        stage_id,
        lease_validator,
    ):
        raise RuntimeError(
            "result publication fenced: "
            "execution authority is no longer valid"
        )

    return metrics
