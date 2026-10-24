"""Causal financial labels for experimental structural model training."""
from __future__ import annotations
from dataclasses import dataclass
from math import log, sqrt, isfinite
from .alphafold_adapter import encode_market


@dataclass(frozen=True)
class StructureSample:
    origin_timestamp: int
    target_timestamp: int
    representation: object
    future_log_return: float
    future_log_volatility: float


def make_samples(symbol, timeframe, timestamps, closes, *,
                 window=16, horizon=5, max_tokens=64):
    if any(type(v) is not int for v in (window, horizon, max_tokens)) or window < 2 or max_tokens < 2:
        raise ValueError("invalid sample configuration")
    if max_tokens > 1024:
        raise ValueError("max_tokens exceeds supported limit")
    if horizon < 2:
        raise ValueError("horizon must be >=2")
    if len(timestamps) != len(closes):
        raise ValueError("timestamps and closes mismatch")
    ts = tuple(timestamps)
    if any(type(t) is not int or t < 0 for t in ts) or any(a >= b for a, b in zip(ts, ts[1:])):
        raise ValueError("timestamps must be strictly increasing integers")
    if len(ts) < window + horizon + 1:
        raise ValueError("insufficient history for supervised samples")
    prices = tuple(float(p) for p in closes)
    if any(not isfinite(p) or p <= 0 for p in prices):
        raise ValueError("prices must be positive finite")
    out = []
    for origin in range(window, len(prices) - horizon):
        # Representation is restricted to history at the forecast origin.
        rep = encode_market(symbol, timeframe, timestamps[:origin + 1],
                            prices[:origin + 1], window=window,
                            max_tokens=max_tokens)
        future = [log(prices[j] / prices[j - 1])
                  for j in range(origin + 1, origin + horizon + 1)]
        avg = sum(future) / horizon
        variance = sum((x - avg) ** 2 for x in future) / horizon
        out.append(StructureSample(
            int(timestamps[origin]), int(timestamps[origin + horizon]),
            rep, log(prices[origin + horizon] / prices[origin]),
            log(max(sqrt(variance), 1e-12))))
    return tuple(out)
