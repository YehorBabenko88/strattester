"""Independent temporal partition oracle for strict research holdout evidence."""
from dataclasses import dataclass

@dataclass(frozen=True)
class LabelInterval:
    instrument: str
    timeframe_ns: int
    decision_ns: int
    end_ns: int

def validate_folds(folds, *, allow_prior_oos_retraining=False):
    if type(allow_prior_oos_retraining) is not bool:
        raise ValueError("invalid retraining policy")
    folds = list(folds)
    if not folds:
        raise ValueError("no folds")
    prior_oos = []
    last_oos_end = -1
    for train, validation, test in folds:
        if not train or not validation or not test:
            raise ValueError("empty fold partition")
        for partition in (train, validation, test):
            for row in partition:
                if (not isinstance(row, LabelInterval) or not row.instrument
                        or any(type(t) is not int or t < 0 for t in
                               (row.timeframe_ns, row.decision_ns, row.end_ns))
                        or row.timeframe_ns == 0 or row.end_ns <= row.decision_ns):
                    raise ValueError("invalid label interval")
        def overlaps(a, b):
            return a.decision_ns < b.end_ns and b.decision_ns < a.end_ns
        if any(overlaps(a, b) for a in train for b in validation + test):
            raise ValueError("train label overlaps evaluation")
        if any(overlaps(a, b) for a in validation for b in test):
            raise ValueError("validation label overlaps test")
        start = min(x.decision_ns for x in test)
        end = max(x.end_ns for x in test)
        if start < last_oos_end:
            raise ValueError("OOS windows overlap or are unordered")
        if not allow_prior_oos_retraining and any(overlaps(x, y) for x in train + validation for y in prior_oos):
            raise ValueError("prior OOS reused")
        prior_oos.extend(test)
        last_oos_end = end
    return {"status": "TEMPORAL_ORACLE_ONLY", "fold_count": len(folds),
            "sequential_retraining": allow_prior_oos_retraining}
