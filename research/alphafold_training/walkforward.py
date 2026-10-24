"""Strict offline walk-forward baseline evaluation.

Each fold fits a fresh model on its own training partition. Validation selects
thresholds. Test outcomes are never fed back into fitting or threshold selection.
"""
from __future__ import annotations
from research.alphafold_training.comparison import compare_baselines
from research.alphafold_training.evaluation import purged_split, validate
from research.alphafold_training.gates import assert_disjoint_windows

def compare_walk_forward(samples, configs):
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
    reports = [compare_baselines(rows, cfg) for cfg in settings]
    # Report fold-level results; do not average overlapping or heterogenous PnL.
    return {"status": "RESEARCH_UNVERIFIED", "fold_count": len(reports),
            "folds": reports, "aggregation": "NOT_AUTHORIZED_WITHOUT_PORTFOLIO_LEDGER"}
