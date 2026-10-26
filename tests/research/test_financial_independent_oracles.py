"""Independent financial oracle regressions against integrated PR #21.

All tests are offline and require no market credentials or databases.
"""
import math
import unittest

from strattester.research.financial_evaluation import Trade, evaluate_ledger, gaussian_scores
from research.alphafold_training.independent_oracles import (
    reference_roundtrip, reference_gaussian, reference_interval_overlap,
)

class IntegratedFinancialOracleTests(unittest.TestCase):
    def test_long_short_flat_roundtrip_oracle(self):
        for position in (-1, 0, 1):
            with self.subTest(position=position):
                observed = evaluate_ledger([Trade("BTC", 1, 2, .012, position)],
                                           fee_bps=7, slippage_bps=3, funding_bps=2)
                expected = reference_roundtrip(position, .012, 7, 3, -position * 2 / 10000)
                self.assertAlmostEqual(observed["returns"][0], expected)

    def test_gaussian_closed_form_oracle(self):
        observed = gaussian_scores([0.], [1.], [0.])
        expected = reference_gaussian(0., 1., 0.)
        self.assertAlmostEqual(observed["nll"], expected["nll"])
        self.assertEqual(observed["coverage_95"], float(expected["covered_95"]))

    def test_boundary_intervals_half_open(self):
        self.assertFalse(reference_interval_overlap((1, 3), (3, 5)))
        self.assertTrue(reference_interval_overlap((1, 4), (3, 5)))

    def test_invalid_funding_fail_closed(self):
        with self.assertRaises(ValueError):
            evaluate_ledger([Trade("BTC", 1, 2, .01, 1)], funding_bps=float("nan"))

if __name__ == "__main__":
    unittest.main()
