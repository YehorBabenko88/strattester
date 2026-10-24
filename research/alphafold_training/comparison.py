"""Independent offline baseline comparison, never used for OOS model selection."""
from __future__ import annotations
from research.alphafold_training.baselines import MeanReturnBaseline, RidgeBaseline
from research.alphafold_training.evaluation import purged_split, validate, fingerprint
from research.alphafold_training.gates import (
    assert_feature_schema, assert_no_cross_partition_label_overlap, assert_prediction_contract,
)
from research.alphafold_training.runner import ResearchConfig, _check_intervals, _score

def compare_baselines(samples, cfg: ResearchConfig):
    """Fit each baseline on train; select threshold on validation; evaluate test once.

    Returns research-only results. No model trained on test; no external I/O.
    """
    validate(samples)
    ordered = sorted(samples, key=lambda s: (s.decision_time, s.instrument))
    train, val, test = purged_split(ordered, cfg.train_end, cfg.validation_end, cfg.test_end, cfg.embargo)
    if not all((train, val, test)):
        raise ValueError("empty partition")
    assert_feature_schema(train + val + test)
    assert_no_cross_partition_label_overlap(train, val, test)
    _check_intervals(val)
    _check_intervals(test)
    if any(not isinstance(c, (int, float)) or c < 0 or c != c or c == float("inf")
           for c in (cfg.fee_bps, cfg.slippage_bps)):
        raise ValueError("invalid execution costs")
    thresholds = (0., .0005, .001, .002)
    output = {}
    for name, factory in (("mean_return", MeanReturnBaseline), ("ridge", RidgeBaseline)):
        model = factory()
        model.fit([s.features for s in train], [s.forward_return for s in train])
        vp = list(model.predict([s.features for s in val]))
        assert_prediction_contract(vp, val)
        def positions(pred, threshold):
            return [int(x > threshold) - int(x < -threshold) for x in pred]
        threshold = max(thresholds, key=lambda t: _score(val, positions(vp, t), cfg)["mean_net_return"])
        # Request test predictions only after threshold selection is finalized.
        tp = list(model.predict([s.features for s in test]))
        assert_prediction_contract(tp, test)
        output[name] = {
            "selected_validation_threshold": threshold,
            "validation": _score(val, positions(vp, threshold), cfg),
            "test": _score(test, positions(tp, threshold), cfg),
        }
    return {"status": "RESEARCH_UNVERIFIED",
            "dataset_sha256": fingerprint([s.__dict__ for s in ordered]),
            "train_count": len(train), "validation_count": len(val), "test_count": len(test),
            "baselines": output}
