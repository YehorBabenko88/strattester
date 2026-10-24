import pytest
from research.independent_watermark_oracle import validate_watermark_sequence,validate_snapshot_cutoff

def test_monotone_watermark_allows_equal_values():
    assert validate_watermark_sequence([0,0,10,20,20])==20

def test_regression_and_future_cutoff_rejected():
    with pytest.raises(ValueError,match='regressing'):
        validate_watermark_sequence([0,10,9])
    with pytest.raises(ValueError,match='future'):
        validate_snapshot_cutoff(101,100,99)
    with pytest.raises(ValueError,match='future'):
        validate_snapshot_cutoff(90,100,101)

def test_boolean_timestamp_rejected():
    with pytest.raises(ValueError):
        validate_watermark_sequence([True])
