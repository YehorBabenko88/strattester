"""Fail-closed funding schedule completeness oracle for a producer-specified cadence.

An expected cadence must be independently justified. This proves only that a
finite timestamp grid is present, not that exchange data is truthful.
"""
from research.alphafold_training.authenticated_funding import FundingRecord

def check_funding_schedule(records, *, instrument, start_ns, end_ns, cadence_ns,
                           first_event_ns, max_expected=100000):
    if any(type(v) is not int for v in (start_ns, end_ns, cadence_ns, first_event_ns, max_expected)):
        raise ValueError("integer schedule required")
    if not 0 <= start_ns < end_ns or cadence_ns <= 0 or first_event_ns < 0 or max_expected < 1:
        raise ValueError("invalid schedule")
    if not isinstance(instrument, str) or not instrument:
        raise ValueError("invalid instrument")
    if first_event_ns < start_ns or first_event_ns > end_ns:
        raise ValueError("first event outside coverage")
    count = (end_ns - first_event_ns) // cadence_ns + 1
    if count > max_expected:
        raise ValueError("funding schedule resource budget")
    expected = {first_event_ns + i * cadence_ns for i in range(count)}
    actual = set()
    for row in records:
        if not isinstance(row, FundingRecord):
            raise ValueError("invalid funding record")
        if row.instrument == instrument and start_ns <= row.event_ns <= end_ns:
            if row.event_ns in actual:
                raise ValueError("duplicate funding timestamp")
            actual.add(row.event_ns)
    if actual != expected:
        raise ValueError("missing or unexpected funding events")
    return {"status": "SCHEDULE_GRID_COMPLETE_ONLY",
            "instrument": instrument, "expected_count": count,
            "exchange_truth_verified": False}
