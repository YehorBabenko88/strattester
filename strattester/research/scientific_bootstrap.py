"""Historical scientific bootstrap exported for Bybit Cluster Grid.

Uses only historically available datasets. L2/liquidations are explicitly absent.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import json,hashlib,time
from .volatility import VolatilityObservatory
from .orderflow import cumulative_delta
from .volume_profile import proxy_profile
from .smc import market_structure
from .scalp_bootstrap import historical_scalp_events
from .scientific_graph import ScientificGraph,observation_artifact,volatility_artifact,nonlinear_evidence_artifact,regime_artifact

HISTORICAL_CAPABILITIES={
    "candles":True,
    "mark_price":True,
    "index_price":True,
    "premium_index":True,
    "open_interest":True,
    "funding":True,
    "long_short_ratio":True,
    "public_trade_aggregates":True,
    "true_l2_orderbook":False,
    "liquidations":False,
    "true_l2_absorption":False,
}

def _bars(store,symbol,start_ms=None,end_ms=None):
    return [
        {
            "t":x.open_time,
            "open":x.open,
            "high":x.high,
            "low":x.low,
            "close":x.close,
            "volume":x.volume,
            "turnover":x.turnover or 0.0,
        }
        for x in store.iter_candles(
            symbol,
            "1m",
            start_ms=start_ms,
            end_ms=end_ms,
        )
    ]


def _trade_aggs(store,symbol,start_ms=None,end_ms=None):
    return list(
        store.iter_public_trade_aggregates(
            symbol,
            "1m",
            start_ms=start_ms,
            end_ms=end_ms,
        )
    )


def _coverage_quality(
    store,
    symbol,
    dataset,
    *,
    start_ms=None,
    end_ms=None,
    timeframe="1m",
    step_ms=60_000,
):
    """
    Classify actual stored coverage without converting absence into data.

    COMPLETE_HISTORY is emitted only when the caller supplied an explicit
    window and the store covers every expected step of that window.

    When no complete requested window is known, OBSERVED_RANGE_ONLY is
    deliberately not treated as COMPLETE_HISTORY.
    """
    cov=store.coverage(
        symbol,
        dataset,
        timeframe,
        step_ms=step_ms,
        start_ms=start_ms,
        end_ms=end_ms,
    )

    if cov.count==0:
        return "MISSING"

    if cov.gaps:
        return "PARTIAL_HISTORY"

    if start_ms is None or end_ms is None:
        return "OBSERVED_RANGE_ONLY"

    start_ms=int(start_ms)
    end_ms=int(end_ms)

    if end_ms < start_ms:
        return "INVALID_WINDOW"

    if cov.earliest is None or cov.latest is None:
        return "MISSING"

    if cov.earliest > start_ms or cov.latest < end_ms:
        return "PARTIAL_HISTORY"

    expected=((end_ms-start_ms)//step_ms)+1

    if cov.count < expected:
        return "PARTIAL_HISTORY"

    return "COMPLETE_HISTORY"


def build_symbol_science(
    store,
    symbol,
    start_ms=None,
    end_ms=None,
):
    candle_quality=_coverage_quality(
        store,
        symbol,
        "candles",
        start_ms=start_ms,
        end_ms=end_ms,
    )

    bars=_bars(
        store,
        symbol,
        start_ms,
        end_ms,
    )

    # nonlinear_evidence_artifact requires at least 40 returns.
    # N candles produce N-1 returns, therefore the scientific pipeline
    # requires at least 41 candle samples before graph construction.
    minimum_scientific_bars=41

    if len(bars)<minimum_scientific_bars:
        return {
            "symbol":symbol,
            "status":"INSUFFICIENT",
            "samples":len(bars),
            "data_quality":{
                "candles":candle_quality,
                "public_trade_aggregates":"NOT_EVALUATED",
            },
            "reason":(
                f"fewer than {minimum_scientific_bars} "
                "candle samples required by scientific graph"
            ),
        }

    # Missing/gapped candles in a requested research window are not a
    # backtest result. Do not calculate returns or scientific evidence from
    # a structurally incomplete requested interval.
    if candle_quality in (
        "MISSING",
        "PARTIAL_HISTORY",
        "INVALID_WINDOW",
    ):
        return {
            "symbol":symbol,
            "status":"INSUFFICIENT",
            "samples":len(bars),
            "from_ms":bars[0]["t"],
            "through_ms":bars[-1]["t"],
            "data_quality":{
                "candles":candle_quality,
                "public_trade_aggregates":"NOT_EVALUATED",
            },
            "reason":"requested candle history is incomplete",
        }

    # Trade aggregates are evaluated against the actual candle interval.
    # This prevents missing order-flow history from silently becoming zero.
    trade_start=(
        int(start_ms)
        if start_ms is not None
        else int(bars[0]["t"])
    )

    trade_end=(
        int(end_ms)
        if end_ms is not None
        else int(bars[-1]["t"])
    )

    trade_quality=_coverage_quality(
        store,
        symbol,
        "public_trade_aggregates",
        start_ms=trade_start,
        end_ms=trade_end,
    )

    trades=_trade_aggs(
        store,
        symbol,
        trade_start,
        trade_end,
    )

    trade_ready=(
        trade_quality=="COMPLETE_HISTORY"
    )

    vol=VolatilityObservatory(
        window=20,
        percentile_lookback=252,
    ).snapshots(
        bars,
        bar_ms=60000,
    )

    # Never fabricate "zero order flow" from absent data.
    flow=(
        cumulative_delta(trades)
        if trade_ready
        else ()
    )

    smc=market_structure(
        bars,
        bar_ms=60000,
    )

    # Scalp events that depend on historical trade aggregates are not
    # evaluated unless that dataset is complete for the candle window.
    scalp=(
        historical_scalp_events(
            bars,
            trades,
            symbol=symbol,
            bar_ms=60000,
        )
        if trade_ready
        else []
    )

    poc=None

    try:
        poc=asdict(
            proxy_profile(
                bars,
                known_at=bars[-1]["t"],
            )
        )
    except ValueError:
        pass

    returns=[]

    for a,b in zip(bars,bars[1:]):
        returns.append(
            (b["close"]/a["close"]-1.0)
            if a["close"]
            else 0.0
        )

    def mean(xs):
        return sum(xs)/len(xs) if xs else None

    delta=[
        float(x.get("delta",0))
        for x in flow
    ]

    graph=ScientificGraph()

    obs=graph.add(
        observation_artifact(
            returns
        )
    )

    vol_model=graph.add(
        volatility_artifact(
            obs,
            returns,
        )
    )

    nonlinear=graph.add(
        nonlinear_evidence_artifact(
            obs,
            returns,
        )
    )

    regime=graph.add(
        regime_artifact(
            vol_model,
            nonlinear,
        )
    )

    fully_ready=(
        candle_quality=="COMPLETE_HISTORY"
        and trade_quality=="COMPLETE_HISTORY"
    )

    return {
        "symbol":symbol,
        "status":"READY" if fully_ready else "DEGRADED",
        "samples":len(bars),
        "from_ms":bars[0]["t"],
        "through_ms":bars[-1]["t"],
        "data_quality":{
            "candles":candle_quality,
            "public_trade_aggregates":trade_quality,
        },
        "summary":{
            "mean_return":mean(returns),
            "mean_abs_return":mean(
                [abs(x) for x in returns]
            ),
            "volatility_regimes":{
                k:sum(
                    1
                    for x in vol
                    if x.regime.value==k
                )
                for k in (
                    "VERY_LOW",
                    "LOW",
                    "NORMAL",
                    "HIGH",
                    "EXTREME",
                )
            },
            # None means "not evaluable from available history".
            # It must never become 0.0 merely because data is absent.
            "mean_delta":mean(delta),
            "smc_events":len(smc),
            "latest_poc_proxy":poc,
        },
        "scientific_layers":[
            {
                "id":x.artifact_id,
                "method":x.method,
                "layer":x.layer,
                "inputs":x.inputs,
                "payload":dict(x.payload),
                "confidence":x.confidence,
                "warnings":x.warnings,
            }
            for x in graph.artifacts()
        ],
        "features":{
            "volatility":[
                asdict(x)
                for x in vol[-512:]
            ],
            "orderflow":[
                dict(x)
                for x in flow[-1024:]
            ],
            "smc":[
                asdict(x)
                for x in smc[-512:]
            ],
            "scalp_events":scalp[-2048:],
        },
    }


def export_scientific_bootstrap(store,symbols,out_path,start_ms=None,end_ms=None,source_id="strattester"):
    rows=[build_symbol_science(store,str(s).upper(),start_ms,end_ms) for s in symbols]
    payload={
      "schema":1,
      "source":source_id,
      "created_at":time.time(),
      "capabilities":HISTORICAL_CAPABILITIES,
      "research_scope":"HISTORICAL_BOOTSTRAP_ONLY",
      "symbols":rows,
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["sha256"]=hashlib.sha256(raw.encode()).hexdigest()
    p=Path(out_path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(payload,sort_keys=True,indent=2,default=str),encoding="utf-8")
    return payload
