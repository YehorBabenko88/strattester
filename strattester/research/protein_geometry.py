"""Experimental protein-inspired geometry for market time series.

Independent market embedding; NOT AlphaFold inference or trained AlphaFold weights.
All features at index t use observations <= t only.
"""
from __future__ import annotations

from math import isfinite, log, sqrt
from typing import Sequence


def market_backbone(closes: Sequence[float], window: int = 16) -> list[tuple[float, float, float]]:
    """Causal 3D path: rolling return, volatility, and momentum.

    Each coordinate is computed from current and past closes only.
    No external data access, model weights, or trading execution.
    """
    if window < 2:
        raise ValueError("window must be >= 2")
    if len(closes) < window + 1:
        raise ValueError("insufficient close history")
    prices = [float(p) for p in closes]
    if any(not isfinite(p) or p <= 0 for p in prices):
        raise ValueError("closes must be positive finite numbers")
    log_prices = [log(p) for p in prices]
    returns = [log_prices[i] - log_prices[i - 1] for i in range(1, len(prices))]
    points = []
    for end in range(window, len(returns) + 1):
        segment = returns[end - window:end]
        avg = sum(segment) / window
        variance = sum((r - avg) ** 2 for r in segment) / window
        points.append((segment[-1], sqrt(variance), sum(segment)))
    return points


def distance_map(points: Sequence[Sequence[float]]) -> list[list[float]]:
    """Pairwise Euclidean distances, suitable for a contact-map visualization."""
    coords = [tuple(map(float, p)) for p in points]
    if any(len(p) != 3 or any(not isfinite(x) for x in p) for p in coords):
        raise ValueError("points must be finite 3D coordinates")
    return [[sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))
             for q in coords] for p in coords]


def contact_map(points: Sequence[Sequence[float]], threshold: float) -> list[list[bool]]:
    if not isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold must be positive and finite")
    d = distance_map(points)
    return [[i != j and value <= threshold for j, value in enumerate(row)]
            for i, row in enumerate(d)]
