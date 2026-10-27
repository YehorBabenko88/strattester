"""Additional strict acceptance gates for experimental financial ML.

No database, network, model weight loading or live trading.
"""
from __future__ import annotations
from collections import defaultdict
from math import isfinite

def assert_no_cross_partition_label_overlap(train, validation, test):
    """Every earlier label must finish before later partition's first decision.

    Conservative global purge also protects shared market events across instruments.
    """
    for left, right in ((train, validation), (validation, test), (train, test)):
        if left and right and max(s.label_end_time for s in left) > min(s.decision_time for s in right):
            raise ValueError("cross-partition label overlap")

def assert_feature_schema(samples):
    if not samples:
        raise ValueError("empty samples")
    n = len(samples[0].features)
    if n == 0:
        raise ValueError("empty feature vector")
    for s in samples:
        if len(s.features) != n or not all(isfinite(x) for x in s.features):
            raise ValueError("inconsistent or nonfinite features")

def assert_prediction_contract(predictions, samples):
    if len(predictions) != len(samples):
        raise ValueError("prediction count mismatch")
    for x in predictions:
        if isinstance(x, bool) or not isinstance(x, (float, int)) or not isfinite(x):
            raise ValueError("prediction must be finite scalar")

def assert_disjoint_windows(windows):
    """Validate increasing walk-forward test windows (no repeated OOS decisions)."""
    seen = set()
    previous_end = None
    for train, validation, test in windows:
        assert_no_cross_partition_label_overlap(train, validation, test)
        assert_feature_schema(train + validation + test)
        if not train or not validation or not test:
            raise ValueError("empty fold")
        start = min(s.decision_time for s in test)
        end = max(s.label_end_time for s in test)
        if previous_end is not None and start < previous_end:
            raise ValueError("overlapping OOS windows")
        previous_end = end
        for s in test:
            key = (s.instrument, s.decision_time)
            if key in seen:
                raise ValueError("duplicate OOS sample")
            seen.add(key)
    if not seen:
        raise ValueError("no OOS observations")
