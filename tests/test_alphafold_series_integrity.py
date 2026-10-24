import pytest

from strattester.alphafold_series_integrity import (
    DataIntegrityError, validate_regular_series,
)


def bar(event, ingestion=None):
    return {"event_time": event, "ingestion_time": event if ingestion is None else ingestion}


def test_valid_complete_series():
    validate_regular_series(
        [bar(0), bar(60), bar(120)],
        interval=60, knowledge_cutoff=120,
        expected_start=0, expected_end=120,
    )


@pytest.mark.parametrize("events", [
    [0, 60, 60], [0, 120], [60, 0], [0, 60, 30],
])
def test_duplicate_gap_and_reorder_fail(events):
    with pytest.raises(DataIntegrityError):
        validate_regular_series([bar(e) for e in events],
                                interval=60, knowledge_cutoff=500)


def test_late_ingestion_fails():
    with pytest.raises(DataIntegrityError, match="Future"):
        validate_regular_series([bar(60, 300)], interval=60,
                                knowledge_cutoff=100)


def test_missing_boundaries_fail():
    with pytest.raises(DataIntegrityError, match="initial"):
        validate_regular_series([bar(60)], interval=60,
                                knowledge_cutoff=100, expected_start=0)
    with pytest.raises(DataIntegrityError, match="final"):
        validate_regular_series([bar(0)], interval=60,
                                knowledge_cutoff=100, expected_end=60)


def test_empty_series_fails():
    with pytest.raises(DataIntegrityError, match="Empty"):
        validate_regular_series([], interval=60, knowledge_cutoff=100)


@pytest.mark.parametrize("rows", [[bar(-1)], [bar(0, -1)]])
def test_negative_timestamp_fails(rows):
    with pytest.raises(DataIntegrityError, match="Negative"):
        validate_regular_series(rows, interval=60, knowledge_cutoff=100)


@pytest.mark.parametrize("bounds", [
    {"expected_start": True}, {"expected_end": -1},
    {"expected_start": 60, "expected_end": 0},
])
def test_invalid_boundaries_fail(bounds):
    with pytest.raises(ValueError):
        validate_regular_series([bar(0)], interval=60, knowledge_cutoff=100, **bounds)
