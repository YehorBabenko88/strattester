"""Fail-closed temporal data provenance checks for offline research observations."""
from dataclasses import dataclass

@dataclass(frozen=True)
class TemporalObservation:
    instrument: str
    timeframe_ns: int
    decision_ns: int
    label_end_ns: int
    feature_available_ns: int
    revision_available_ns: int
    source_epoch: str

def audit_temporal_observations(rows, *, held_out_instruments=frozenset(),
                                held_out_timeframes=frozenset()):
    observations = list(rows)
    if not observations:
        raise ValueError("empty temporal evidence")
    seen = set()
    for row in observations:
        if not isinstance(row, TemporalObservation):
            raise ValueError("invalid observation type")
        times = (row.timeframe_ns, row.decision_ns, row.label_end_ns,
                 row.feature_available_ns, row.revision_available_ns)
        if any(type(t) is not int or t < 0 for t in times) or row.timeframe_ns <= 0:
            raise ValueError("invalid time")
        if not row.instrument or not row.source_epoch:
            raise ValueError("missing source identity")
        if (row.feature_available_ns > row.decision_ns
                or row.revision_available_ns > row.decision_ns
                or row.label_end_ns <= row.decision_ns):
            raise ValueError("future leakage or invalid label horizon")
        if row.instrument in held_out_instruments or row.timeframe_ns in held_out_timeframes:
            raise ValueError("holdout contamination")
        key = (row.instrument, row.timeframe_ns, row.decision_ns)
        if key in seen:
            raise ValueError("duplicate temporal identity")
        seen.add(key)
    return {"status": "TEMPORAL_CONTRACT_ONLY", "count": len(observations)}
