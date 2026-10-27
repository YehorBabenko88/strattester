import pytest
from research.independent_precision_oracle import float32,assert_precision_close

def test_float32_rounding_tolerance():
    for value in (0.1,1.23456789,1000.123):
        assert assert_precision_close(value,float32(value),dtype='float32')

def test_float64_strict_and_float32_looser():
    with pytest.raises(ValueError,match='tolerance'):
        assert_precision_close(1.,1.000001,dtype='float64')
    assert assert_precision_close(1.,1.000001,dtype='float32')

def test_float32_overflow_and_nonfinite_fail_closed():
    with pytest.raises(ValueError):
        float32(1e100)
    with pytest.raises(ValueError):
        float32(float('nan'))
