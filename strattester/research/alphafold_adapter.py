"""Strict financial-to-AlphaFold-style representation boundary.

No original AlphaFold inference is claimed; neural backend must be supplied
separately, trained on financial labels and validated out of sample.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Protocol, Sequence
from .protein_geometry import market_backbone, distance_map


@dataclass(frozen=True)
class FinancialRepresentation:
    symbol: str
    timeframe: str
    timestamps: tuple[int, ...]
    single: tuple[tuple[float, float, float], ...]
    pair: tuple[tuple[float, ...], ...]
    source_sha256: str


class FinancialStructureBackend(Protocol):
    def predict(self, features: FinancialRepresentation) -> object: ...


def encode_market(symbol: str, timeframe: str, timestamps: Sequence[int],
                  closes: Sequence[float], *, window: int = 16,
                  max_tokens: int = 256) -> FinancialRepresentation:
    if not symbol or not timeframe:
        raise ValueError("symbol and timeframe required")
    if len(timestamps) != len(closes):
        raise ValueError("timestamps/closes mismatch")
    if not 1 <= max_tokens <= 1024:
        raise ValueError("max_tokens out of range")
    ts = tuple(int(t) for t in timestamps)
    if any(t < 0 for t in ts) or any(a >= b for a, b in zip(ts, ts[1:])):
        raise ValueError("timestamps must increase strictly")
    prices = tuple(float(x) for x in closes)
    if any(not isfinite(x) or x <= 0 for x in prices):
        raise ValueError("invalid close")
    # Use complete history for each trailing rolling window; cap quadratic pair tensor.
    points = market_backbone(prices, window=window)[-max_tokens:]
    aligned = ts[len(ts) - len(points):]
    canonical = json.dumps({"symbol": symbol, "timeframe": timeframe,
                            "timestamps": ts, "closes": prices},
                           separators=(",", ":"), allow_nan=False)
    return FinancialRepresentation(
        symbol, timeframe, aligned, tuple(points),
        tuple(tuple(row) for row in distance_map(points)),
        sha256(canonical.encode("utf-8")).hexdigest(),
    )


def predict_with_backend(features: FinancialRepresentation,
                         backend: FinancialStructureBackend) -> object:
    """Explicit injection: no silent fallback to protein weights or heuristics."""
    if backend is None:
        raise RuntimeError("financially trained structural backend is required")
    return backend.predict(features)
