"""Strict offline walk-forward baseline evaluation.

Each fold fits a fresh model on its own training partition. Validation selects
thresholds. Test outcomes are never fed back into fitting or threshold selection.
"""
from __future__ import annotations
from research.alphafold_training.comparison import compare_baselines
from research.alphafold_training.evaluation import purged_split, validate
from research.alphafold_training.gates import assert_disjoint_windows

def compare_walk_forward(samples, configs, *, allow_retraining_on_prior_oos=False):
    """By default, prevent training on any previously reported OOS labels.

    Explicit opt-in represents sequential deployment-style retraining; its
    later folds are not independent holdouts from earlier published OOS.
    """
    rows = list(samples)
    validate(rows)
    settings = list(configs)
    if not settings:
        raise ValueError("at least one fold required")
    windows = [
        purged_split(rows, cfg.train_end, cfg.validation_end, cfg.test_end, cfg.embargo)
        for cfg in settings
    ]
    assert_disjoint_windows(windows)
    if not allow_retraining_on_prior_oos:
        previous_test_keys = set()
        for train, validation, test in windows:
            if any((s.instrument, s.decision_time) in previous_test_keys for s in train + validation):
                raise ValueError("previously reported OOS observation reused for training/validation")
            previous_test_keys.update((s.instrument, s.decision_time) for s in test)
    reports = [compare_baselines(rows, cfg) for cfg in settings]
    # Report fold-level results; do not average overlapping or heterogenous PnL.
    return {"status": "RESEARCH_UNVERIFIED", "fold_count": len(reports),
            "folds": reports, "retraining_on_prior_oos": allow_retraining_on_prior_oos,
            "fold_independence": "SEQUENTIAL_RETRAINING" if allow_retraining_on_prior_oos else "NO_PRIOR_OOS_REUSE",
            "aggregation": "NOT_AUTHORIZED_WITHOUT_PORTFOLIO_LEDGER"}
