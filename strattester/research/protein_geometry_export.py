"""Read-only, offline JSON export of protein-inspired BTC market geometry."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from .protein_geometry import market_backbone, distance_map


def geometry_payload(closes: Sequence[float], timestamps: Sequence[int], *,
                     window: int = 16, symbol: str = "BTCUSDT",
                     max_points: int = 512) -> dict:
    if not symbol or not symbol.isascii() or not symbol.replace("_", "").isalnum():
        raise ValueError("invalid symbol")
    if len(closes) != len(timestamps):
        raise ValueError("timestamp/price length mismatch")
    if not 1 <= max_points <= 2048:
        raise ValueError("max_points out of range")
    times = [int(t) for t in timestamps]
    if any(t < 0 for t in times) or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("timestamps must be strictly increasing and nonnegative")
    # Bound the quadratic distance map, preserving historical causal windows.
    points = market_backbone(closes, window=window)
    offset = len(points) - min(max_points, len(points))
    selected = points[offset:]
    return {
        "schema": "strattester.protein_geometry.v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "model": "independent_market_geometry_not_alphafold",
        "symbol": symbol,
        "window": window,
        "timestamps": times[window + offset:],
        "closes": [float(x) for x in closes[window + offset:]],
        "points": [list(p) for p in selected],
        "distances": distance_map(selected),
    }


def export_json(path: Path, closes: Sequence[float], timestamps: Sequence[int], **kwargs) -> Path:
    """Explicit export to a caller-selected path; never accesses production DBs."""
    payload = geometry_payload(closes, timestamps, **kwargs)
    target = Path(path)
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        json.dump(payload, f, allow_nan=False, separators=(",", ":"))
    return target
