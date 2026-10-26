"""Independent reference oracles for financial research accounting.

Offline only. No execution engine or database interaction.
"""
from __future__ import annotations
from math import exp, isfinite, log, pi, sqrt
from statistics import mean

def reference_roundtrip(position, simple_return, fee_bps, slippage_bps, funding_cashflow=0.):
    """Independent gross-minus-two-fills oracle for one unit notional."""
    if type(position) is not int or position not in (-1, 0, 1):
        raise ValueError("position")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v)
           for v in (simple_return, fee_bps, slippage_bps, funding_cashflow)):
        raise ValueError("nonfinite")
    if simple_return < -1 or fee_bps < 0 or slippage_bps < 0:
        raise ValueError("invalid return or costs")
    entry = abs(position) * (fee_bps + slippage_bps) / 10000
    exit_cost = abs(position) * (fee_bps + slippage_bps) / 10000
    return position * simple_return - entry - exit_cost + position * funding_cashflow

def reference_gaussian(mu, sigma, target):
    """Analytic independent Gaussian NLL, standardized residual and 95% hit."""
    if any(not isfinite(v) for v in (mu, sigma, target)) or sigma <= 0:
        raise ValueError("invalid gaussian")
    z = (target - mu) / sigma
    return {"nll": .5 * log(2 * pi) + log(sigma) + .5 * z * z,
            "z": z, "covered_95": abs(z) <= 1.959963984540054}

def reference_interval_overlap(first, second):
    """Half-open event-time label intervals [decision, label_end)."""
    a, b = first
    c, d = second
    if not a < b or not c < d:
        raise ValueError("invalid interval")
    return a < d and c < b

def reference_calibration(predictions, scales, labels):
    if not predictions or len(predictions) != len(scales) or len(scales) != len(labels):
        raise ValueError("length mismatch")
    values = [reference_gaussian(mu, sigma, y)
              for mu, sigma, y in zip(predictions, scales, labels)]
    return {"nll": mean(v["nll"] for v in values),
            "coverage_95": mean(v["covered_95"] for v in values),
            "standardized_residual_mean": mean(v["z"] for v in values),
            "standardized_residual_second_moment": mean(v["z"] ** 2 for v in values),
            "mean_predicted_scale": mean(scales),
            "status": "EXPLORATORY_NOT_PROFITABILITY_EVIDENCE"}
