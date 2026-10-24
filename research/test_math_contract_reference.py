import math
import unittest
from math_contract_reference import (log_returns, sample_volatility,
    validate_observations, pair_dependency_mask, triangle_path_valid,
    validate_purged_splits, train_only_zscore)


class MathematicalContractTests(unittest.TestCase):
    def test_return_identity(self):
        p = [100, 102, 101, 110]
        for r, a, b in zip(log_returns(p), p, p[1:]):
            self.assertAlmostEqual(math.expm1(r), b / a - 1, places=12)

    def test_extreme_price_ratios_remain_finite(self):
        returns = log_returns([1e-300, 1e300, 1e-300])
        self.assertTrue(all(math.isfinite(x) for x in returns))
        self.assertAlmostEqual(returns[0], -returns[1], places=10)

    def test_invalid_price(self):
        with self.assertRaises(ValueError):
            log_returns([100, 0])

    def test_sample_volatility(self):
        self.assertAlmostEqual(sample_volatility([1, 2, 3]), 1)
        self.assertEqual(sample_volatility([0, 0, 0]), 0)

    def test_no_future_observation(self):
        row = dict(event_id="x", event_time_ns=10, available_time_ns=30,
                   bucket_end_ns=20, eligible=True, quality_status="VERIFIED",
                   gap_status="NONE")
        with self.assertRaises(ValueError):
            validate_observations([row], 25, 20)
        self.assertTrue(validate_observations([row], 30, 20))
        with self.assertRaises(ValueError):
            validate_observations([row, row], 30, 20)

    def test_triangle_intermediate_cannot_leak(self):
        mask = pair_dependency_mask([1, 3, 99], [2, 4, 5])
        self.assertFalse(triangle_path_valid(mask, 1, 0, 2))
        self.assertTrue(triangle_path_valid(mask, 1, 0, 1))



    def test_fail_closed_bad_time_types_and_order(self):
        row = dict(event_id="x", event_time_ns=10, available_time_ns=30,
                   bucket_end_ns=20, eligible=True, quality_status="VERIFIED",
                   gap_status="NONE")
        for mutation in ({"event_time_ns": True}, {"available_time_ns": 19},
                         {"eligible": 1}, {"event_time_ns": -1}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_observations([{**row, **mutation}], 30, 20)
        with self.assertRaises(ValueError):
            validate_observations([row], 20, 21)

    def test_pair_budget_and_invalid_timestamps(self):
        with self.assertRaises(ValueError):
            pair_dependency_mask([1, 2, 3], [1, 2, 3], max_cells=8)
        with self.assertRaises(ValueError):
            pair_dependency_mask([True], [1])
        with self.assertRaises(ValueError):
            pair_dependency_mask([1], [1, 2])

    def test_triangle_rejects_negative_indices_and_nonboolean_masks(self):
        with self.assertRaises(ValueError):
            triangle_path_valid([[True]], -1, 0, 0)
        with self.assertRaises(ValueError):
            triangle_path_valid([[1]], 0, 0, 0)
        with self.assertRaises(ValueError):
            triangle_path_valid([[True, False]], 0, 0, 0)

    def test_purge_overlap_and_embargo(self):
        with self.assertRaises(ValueError):
            validate_purged_splits([(0, 10)], [(10, 20)])
        with self.assertRaises(ValueError):
            validate_purged_splits([(0, 10)], [(12, 20)], embargo_ns=2)
        self.assertTrue(validate_purged_splits([(0, 10)], [(13, 20)], embargo_ns=2))

    def test_train_only_normalization(self):
        values, state = train_only_zscore([0.0, 2.0], [1.0, 100.0])
        self.assertEqual(state, (1.0, 1.0))
        self.assertEqual(values, [0.0, 99.0])
        self.assertEqual(train_only_zscore([2.0, 2.0], [2.0])[0], [0.0])
        with self.assertRaises(ValueError):
            train_only_zscore([2.0, 2.0], [100.0])


if __name__ == "__main__":
    unittest.main()
