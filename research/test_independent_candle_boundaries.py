import pytest
from research.independent_candle_boundaries import inclusive_last_ms_to_exclusive_end_ns, validate_bucket_alignment

def test_one_minute_inclusive_exchange_close():
    assert inclusive_last_ms_to_exclusive_end_ns(59_999) == 60_000_000_000
    assert validate_bucket_alignment(0,60_000_000_000,60_000_000_000)

def test_misaligned_and_partial_buckets_fail_closed():
    with pytest.raises(ValueError):
        validate_bucket_alignment(1,60_000_000_001,60_000_000_000)
    with pytest.raises(ValueError):
        validate_bucket_alignment(0,59_999_000_000,60_000_000_000)

def test_invalid_last_timestamp():
    with pytest.raises(ValueError):
        inclusive_last_ms_to_exclusive_end_ns(-1)
