"""Leakage-aware, dependency-free research evaluation primitives.

Inputs are immutable observations with explicitly declared feature availability.
This module does not train AlphaFold or connect to production databases.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import random
from statistics import mean

@dataclass(frozen=True)
class Sample:
    instrument: str
    decision_time: int
    label_end_time: int
    available_at: int
    features: tuple[float, ...]
    forward_return: float

def validate(samples):
    seen = set()
    for s in samples:
        key = (s.instrument, s.decision_time)
        if (not s.instrument or not all(isinstance(t, int) and not isinstance(t, bool) for t in (s.decision_time, s.label_end_time, s.available_at))
                or key in seen or s.label_end_time <= s.decision_time or s.available_at > s.decision_time):
            raise ValueError("duplicate sample, invalid label interval, or future feature")
        if not math.isfinite(s.forward_return) or any(not math.isfinite(x) for x in s.features):
            raise ValueError("non-finite data")
        seen.add(key)

def purged_split(samples, train_end, validation_end, test_end, embargo=0):
    """Chronological boundaries, label-interval purge and explicit embargo."""
    if not 0 < train_end < validation_end < test_end or embargo < 0:
        raise ValueError("invalid boundaries")
    validate(samples)
    train = [s for s in samples if s.decision_time < train_end and s.label_end_time + embargo <= train_end]
    validation = [s for s in samples if train_end <= s.decision_time < validation_end
                  and s.label_end_time + embargo <= validation_end]
    test = [s for s in samples if validation_end <= s.decision_time < test_end
            and s.label_end_time <= test_end]
    return train, validation, test

def walk_forward(samples, boundaries, embargo=0):
    """Yield expanding train / validation / test folds, with nonoverlapping labels."""
    for a, b, c in boundaries:
        yield purged_split(samples, a, b, c, embargo)

def fingerprint(records):
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(payload.encode("utf-8")).hexdigest()

def net_returns(samples, positions, fee_bps, slippage_bps):
    """One decision per independent horizon; fee and slippage per position change."""
    if (len(samples) != len(positions) or not all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) and c >= 0 for c in (fee_bps, slippage_bps))):
        raise ValueError("invalid execution inputs")
    validate(samples)
    if list(samples) != sorted(samples, key=lambda s: (s.decision_time, s.instrument)):
        raise ValueError("execution samples must be ordered by decision time")
    out, previous = [], {}
    for s, p in zip(samples, positions):
        if type(p) is not int or p not in (-1, 0, 1):
            raise ValueError("positions must be -1, 0, 1")
        turnover = abs(p - previous.get(s.instrument, 0))
        out.append(p * s.forward_return - turnover * (fee_bps + slippage_bps) / 10000)
        previous[s.instrument] = p
    return out

def bootstrap_mean_ci(values, *, block_size=5, repetitions=1000, seed=0, alpha=0.05):
    """Moving-block bootstrap; exploratory only, not a guarantee of coverage."""
    if not values or block_size < 1 or repetitions < 2 or not 0 < alpha < 1:
        raise ValueError("invalid bootstrap arguments")
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) for x in values):
        raise ValueError("bootstrap requires finite numeric values")
    n = len(values)
    rng = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        resampled = []
        while len(resampled) < n:
            start = rng.randrange(n)
            resampled.extend(values[(start + j) % n] for j in range(block_size))
        estimates.append(mean(resampled[:n]))
    estimates.sort()
    return estimates[int(alpha / 2 * repetitions)], estimates[min(repetitions - 1, int((1 - alpha / 2) * repetitions))]

def negative_control(positions, seed=0):
    """Permute model signals within the evaluated slice."""
    shuffled = list(positions)
    random.Random(seed).shuffle(shuffled)
    return shuffled

def per_instrument(samples, returns):
    if len(samples) != len(returns):
        raise ValueError("length mismatch")
    groups = {}
    for s, value in zip(samples, returns):
        groups.setdefault(s.instrument, []).append(value)
    return {key: {"count": len(vals), "mean_net_return": mean(vals)}
            for key, vals in sorted(groups.items())}

def registry_record(*, dataset_sha256, model_sha256, config, metrics):
    for digest in (dataset_sha256, model_sha256):
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("invalid SHA256")
    return {"schema_version": 1, "dataset_sha256": dataset_sha256,
            "model_sha256": model_sha256, "config": config, "metrics": metrics,
            "status": "RESEARCH_UNVERIFIED"}
