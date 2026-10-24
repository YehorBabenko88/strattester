import math

import pytest

from strattester.research.protein_geometry import contact_map, distance_map, market_backbone


def test_shapes_and_symmetry():
    points = market_backbone([100 + i * .2 for i in range(40)], window=6)
    assert len(points) == 34
    matrix = distance_map(points)
    assert len(matrix) == len(points)
    for i in range(len(points)):
        assert matrix[i][i] == 0
        for j in range(len(points)):
            assert matrix[i][j] == pytest.approx(matrix[j][i])
    contacts = contact_map(points, .01)
    assert all(not contacts[i][i] for i in range(len(points)))


def test_prefix_invariance_prevents_future_leakage():
    prefix = [100 + math.sin(i / 3) for i in range(32)]
    first = market_backbone(prefix, window=8)
    extended = market_backbone(prefix + [500, 200, 1000], window=8)
    assert extended[:len(first)] == first


@pytest.mark.parametrize("prices", [[1, 0, 3], [1, -1, 3], [1, float("nan"), 3]])
def test_reject_bad_prices(prices):
    with pytest.raises(ValueError):
        market_backbone(prices, window=2)


def test_reject_nonfinite_coordinates_and_threshold():
    with pytest.raises(ValueError):
        distance_map([(0, float("inf"), 0)])
    with pytest.raises(ValueError):
        contact_map([(0, 0, 0)], 0)


def test_extreme_finite_prices_do_not_overflow_log_returns():
    prices = [1e-300 if i % 2 else 1e300 for i in range(16)]
    points = market_backbone(prices, window=4)
    assert len(points) == len(prices) - 4
    assert all(math.isfinite(value) for point in points for value in point)
