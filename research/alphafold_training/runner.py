"""Fail-closed offline research runner: explicit fit/predict interface and OOS accounting."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from statistics import mean
import math

from research.alphafold_training.evaluation import (
    validate, purged_split, net_returns, per_instrument, bootstrap_mean_ci,
    fingerprint, negative_control,
)

@dataclass(frozen=True)
class ResearchConfig:
    train_end: int
    validation_end: int
    test_end: int
    embargo: int = 0
    fee_bps: float = 0
    slippage_bps: float = 0
    seed: int = 0

def verify_artifact(path, expected_sha256):
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("invalid digest")
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise ValueError("artifact must be an ordinary file")
    h = sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_sha256:
        raise ValueError("artifact SHA256 mismatch")
    return True

def _check_intervals(samples):
    """Reject overlapping holding horizons per instrument, rather than double count PnL."""
    last = {}
    for s in sorted(samples, key=lambda x: (x.instrument, x.decision_time)):
        if s.decision_time < last.get(s.instrument, -math.inf):
            raise ValueError("overlapping evaluation labels: no portfolio simulator")
        last[s.instrument] = s.label_end_time

def _score(samples, positions, cfg):
    _check_intervals(samples)
    pnl = net_returns(samples, positions, cfg.fee_bps, cfg.slippage_bps)
    if not pnl:
        raise ValueError("empty evaluation slice")
    return {"count": len(pnl), "mean_net_return": mean(pnl),
            "by_instrument": per_instrument(samples, pnl),
            "exploratory_mean_ci": bootstrap_mean_ci(pnl, seed=cfg.seed,
                                                       block_size=min(5, len(pnl)))}

def evaluate_offline(samples, model_factory, cfg):
    """Fit on training only, choose threshold on validation, test once.

    model_factory() must return an isolated model with fit(X,y) and predict(X).
    Predictions are numerical forward-return estimates; zero baseline is explicit.
    This function does not claim statistical significance or profitability.
    """
    validate(samples)
    if not all(math.isfinite(v) and v >= 0 for v in (cfg.fee_bps, cfg.slippage_bps)):
        raise ValueError("invalid costs")
    ordered = sorted(samples, key=lambda s: (s.decision_time, s.instrument))
    train, val, test = purged_split(ordered, cfg.train_end, cfg.validation_end,
                                    cfg.test_end, cfg.embargo)
    if not train or not val or not test:
        raise ValueError("all temporal partitions must be nonempty")
    _check_intervals(val)
    _check_intervals(test)
    model = model_factory()
    model.fit([s.features for s in train], [s.forward_return for s in train])
    val_pred = list(model.predict([s.features for s in val]))
    test_pred = list(model.predict([s.features for s in test]))
    if len(val_pred) != len(val) or len(test_pred) != len(test):
        raise ValueError("prediction length mismatch")
    if any(not math.isfinite(float(x)) for x in val_pred + test_pred):
        raise ValueError("nonfinite prediction")
    thresholds = (0., 0.0005, 0.001, 0.002)
    def positions(pred, threshold):
        return [int(x > threshold) - int(x < -threshold) for x in pred]
    threshold = max(thresholds, key=lambda t: _score(val, positions(val_pred, t), cfg)["mean_net_return"])
    selected = positions(test_pred, threshold)
    return {
        "status": "RESEARCH_UNVERIFIED",
        "dataset_sha256": fingerprint([s.__dict__ for s in ordered]),
        "selection_threshold": threshold,
        "validation_count": len(val),
        "test": _score(test, selected, cfg),
        "zero_baseline": _score(test, [0] * len(test), cfg),
        "shuffled_signal_control": _score(test, negative_control(selected, cfg.seed), cfg),
    }
