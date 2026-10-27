"""Independent randomized metamorphic contract tests; deterministic seeds."""
import random
import math
import pytest
from research.independent_time_oracles import aggregate_closed_bars, ms_to_ns, ns_to_ms_exact
from research.independent_decimal_oracles import decimal_returns

def test_randomized_unit_roundtrips():
    rng = random.Random(20261024)
    for _ in range(500):
        value = rng.randrange(0, 2**62 // 1_000_000)
        assert ns_to_ms_exact(ms_to_ns(value)) == value

def test_randomized_return_telescoping():
    rng = random.Random(47)
    for _ in range(200):
        prices = [math.exp(rng.uniform(-20, 20)) for _ in range(10)]
        values = decimal_returns(prices)
        total = sum((x[0] for x in values))
        assert float(total) == pytest.approx(math.log(prices[-1]) - math.log(prices[0]), abs=1e-12)

def test_timeframe_partition_aggregation_invariant():
    rng = random.Random(101)
    for _ in range(50):
        base = rng.uniform(10, 100)
        bars = []
        for i in range(6):
            nxt = base * (1 + rng.uniform(-.01, .01))
            bars.append((i*60, (i+1)*60, base, max(base,nxt)+1, min(base,nxt)-1, nxt, i+1, (i+1)*60))
            base = nxt
        direct = aggregate_closed_bars(bars, 60, 360, 360)
        left = aggregate_closed_bars(bars[:3], 60, 360, 360)
        right = aggregate_closed_bars(bars[3:], 60, 360, 360)
        assert direct == (left[0], max(left[1],right[1]), min(left[2],right[2]), right[3], left[4]+right[4])
