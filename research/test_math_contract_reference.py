import math
import unittest
from math_contract_reference import (log_returns, sample_volatility,
    validate_observations, pair_dependency_mask, triangle_path_valid)


class MathematicalContractTests(unittest.TestCase):
    def test_return_identity(self):
        p = [100, 102, 101, 110]
        for r, a, b in zip(log_returns(p), p, p[1:]):
            self.assertAlmostEqual(math.expm1(r), b / a - 1, places=12)

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


if __name__ == "__main__":
    unittest.main()
