import pytest
from decimal import Decimal
from research.independent_resampling_oracle_20261026 import aggregate_candles

def bars():
    return [(0,60,60,100,102,99,101,2),(60,120,120,101,105,100,104,3)]

def test_decimal_aggregation():
    assert aggregate_candles(bars(),step_ns=60,factor=2,cutoff_ns=120) == (
        0,120,Decimal(100),Decimal(105),Decimal(99),Decimal(104),Decimal(5))

def test_future_and_gap_rejected():
    with pytest.raises(ValueError):
        aggregate_candles(bars(),step_ns=60,factor=2,cutoff_ns=119)
    gap=list(bars());gap[1]=(61,121,121,101,105,100,104,3)
    with pytest.raises(ValueError):
        aggregate_candles(gap,step_ns=60,factor=2,cutoff_ns=121)

def test_incomplete_and_nonfinite_rejected():
    partial=list(bars());partial[1]=(60,120,119,101,105,100,104,3)
    with pytest.raises(ValueError):
        aggregate_candles(partial,step_ns=60,factor=2,cutoff_ns=120)
    invalid=list(bars());invalid[1]=(60,120,120,101,float('nan'),100,104,3)
    with pytest.raises(ValueError):
        aggregate_candles(invalid,step_ns=60,factor=2,cutoff_ns=120)
