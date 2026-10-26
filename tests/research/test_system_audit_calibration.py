import unittest
from research.alphafold_training.system_audit_calibration import calibration_diagnostics
from strattester.research.financial_evaluation import gaussian_scores

class CalibrationOracleTests(unittest.TestCase):
    def test_coverage_matches_existing_gaussian_score(self):
        mu = [0., 0., 0., 0.]
        scale = [1., 1., 1., 1.]
        targets = [0., .5, 2., -3.]
        oracle = calibration_diagnostics(mu, scale, targets)
        observed = gaussian_scores(mu, scale, targets)
        self.assertEqual(oracle["coverage_95"], observed["coverage_95"])
        self.assertEqual(oracle["mean_squared_standardized_residual"], (0 + .25 + 4 + 9) / 4)
        self.assertEqual(oracle["count"], 4)

    def test_extreme_and_nonfinite_rejected(self):
        for target in (float("nan"), float("inf"), 1e308):
            with self.subTest(target=target), self.assertRaises(ValueError):
                calibration_diagnostics([0.], [1e-308], [target])

    def test_zero_scale_rejected(self):
        with self.assertRaises(ValueError):
            calibration_diagnostics([0.], [0.], [0.])

if __name__ == "__main__":
    unittest.main()
