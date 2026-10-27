import math
import unittest
from research.alphafold_training.independent_oracles import (
    reference_roundtrip, reference_gaussian, reference_interval_overlap,
    reference_calibration,
)

class IndependentOracleTests(unittest.TestCase):
    def test_two_fills_and_signed_funding(self):
        self.assertAlmostEqual(reference_roundtrip(1, .01, 10, 5, -.002), .005)
        self.assertAlmostEqual(reference_roundtrip(-1, .01, 10, 5, -.002), -.011)

    def test_zero_position_zero_cost(self):
        self.assertEqual(reference_roundtrip(0, .02, 10, 5, 0), 0)

    def test_gaussian_closed_form(self):
        result = reference_gaussian(0., 1., 0.)
        self.assertAlmostEqual(result["nll"], .5 * math.log(2 * math.pi))
        self.assertTrue(result["covered_95"])

    def test_half_open_overlap(self):
        self.assertFalse(reference_interval_overlap((1, 3), (3, 5)))
        self.assertTrue(reference_interval_overlap((1, 4), (3, 5)))

    def test_calibration_report(self):
        result = reference_calibration([0., 0.], [1., 1.], [0., 2.])
        self.assertEqual(result["coverage_95"], .5)
        self.assertEqual(result["standardized_residual_second_moment"], 2.)
        self.assertEqual(result["status"], "EXPLORATORY_NOT_PROFITABILITY_EVIDENCE")

if __name__ == "__main__":
    unittest.main()
