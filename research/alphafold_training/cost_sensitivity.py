"""Deterministic cost sensitivity on frozen predictions and positions.

Research accounting only. No trading, order routing or portfolio claims.
"""
from __future__ import annotations
from math import isfinite
from statistics import mean
from research.alphafold_training.evaluation import net_returns, per_instrument, validate
from research.alphafold_training.runner import _check_intervals

def cost_sensitivity(samples, positions, scenarios):
    """Apply fixed positions to fee/slippage scenarios without refitting a model.

    Scenarios are pairs of (fee_bps, slippage_bps). Costs must be finite,
    nonnegative, and no scenario can alter signal selection.
    """
    rows = list(samples)
    signals = list(positions)
    validate(rows)
    _check_intervals(rows)
    if not rows or len(rows) != len(signals):
        raise ValueError("invalid observations or positions")
    if rows != sorted(rows, key=lambda s: (s.decision_time, s.instrument)):
        raise ValueError("observations must be chronological")
    scenarios = list(scenarios)
    if not scenarios:
        raise ValueError("no cost scenarios")
    result = []
    for scenario in scenarios:
        if (not isinstance(scenario, (tuple, list)) or len(scenario) != 2
                or any(not isinstance(x, (int, float)) or isinstance(x, bool)
                       or not isfinite(x) or x < 0 for x in scenario)):
            raise ValueError("invalid cost scenario")
        fee, slip = scenario
        pnl = net_returns(rows, signals, fee, slip)
        result.append({
            "fee_bps": fee, "slippage_bps": slip,
            "count": len(pnl), "mean_net_return": mean(pnl),
            "by_instrument": per_instrument(rows, pnl),
        })
    return {"status": "RESEARCH_UNVERIFIED",
            "positions_frozen": True,
            "scenarios": result}
