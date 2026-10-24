import pytest
from decimal import Decimal
from research.independent_horizon_oracle import horizon_target

def test_target_horizon_and_availability():
    bars = [(i*60,(i+1)*60,100+i,(i+1)*60+5) for i in range(10)]
    result = horizon_target(bars,2,3)
    assert result['origin_available_ns'] == 185
    assert result['target_available_ns'] == 365
    assert result['simple_return'] == Decimal(105)/Decimal(102)-1

def test_target_horizon_does_not_use_intermediate_future_as_origin():
    bars = [(i*60,(i+1)*60,100+i,(i+1)*60) for i in range(8)]
    before = horizon_target(bars,1,3)
    changed = list(bars)
    changed[3] = (180,240,999,240)
    assert horizon_target(changed,1,3) == before

def test_gap_and_invalid_horizon_fail_closed():
    bars = [(0,60,100,60),(61,120,101,120),(120,180,102,180)]
    with pytest.raises(ValueError):
        horizon_target(bars,0,2)
    with pytest.raises(ValueError):
        horizon_target(bars,0,3)
