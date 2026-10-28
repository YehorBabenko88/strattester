import pytest
from research.independent_time_oracles import ms_to_ns, ns_to_ms_exact, validate_candle, aggregate_closed_bars

def test_unit_round_trip_and_precision():
    for ms in (0, 1, 1_700_000_000_123, 2**53):
        assert ns_to_ms_exact(ms_to_ns(ms)) == ms
    with pytest.raises(ValueError):
        ns_to_ms_exact(1_000_001)

def test_pit_candle_cutoff_and_watermark():
    assert validate_candle(0, 60, 65, 70, 60)
    for args in ((0, 60, 71, 70, 60), (0, 60, 65, 70, 59), (60, 60, 60, 70, 60)):
        with pytest.raises(ValueError):
            validate_candle(*args)

def test_cross_timeframe_aggregation_and_gaps():
    bars = [(0,60,10,12,9,11,2,60), (60,120,11,14,10,13,3,120)]
    assert aggregate_closed_bars(bars, 60, 120, 120) == (10,14,9,13,5)
    with pytest.raises(ValueError):
        aggregate_closed_bars([bars[0], (61,121,11,14,10,13,3,121)],60,130,130)

def test_future_unavailable_bar_cannot_aggregate():
    with pytest.raises(ValueError):
        aggregate_closed_bars([(0,60,10,12,9,11,2,100)],60,90,60)
