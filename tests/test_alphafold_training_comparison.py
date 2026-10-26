import unittest
from research.alphafold_training.comparison import compare_baselines
from research.alphafold_training.evaluation import Sample
from research.alphafold_training.runner import ResearchConfig

class ComparisonTests(unittest.TestCase):
    def test_report_has_both_independent_baselines(self):
        rows = [Sample("BTC", t, t + 1, t, (float(t),), .001 * t)
                for t in (1, 3, 5, 11, 13, 15, 21, 23, 25)]
        cfg = ResearchConfig(10, 20, 30)
        report = compare_baselines(rows, cfg)
        self.assertEqual(set(report["baselines"]), {"mean_return", "ridge"})
        self.assertEqual(report["test_count"], 3)
        self.assertEqual(report, compare_baselines(rows, cfg))

    def test_cross_instrument_overlap_fails(self):
        rows = [
            Sample("BTC", 1, 14, 1, (1.,), .01),
            Sample("ETH", 12, 13, 12, (2.,), .01),
            Sample("ETH", 21, 22, 21, (3.,), .01),
        ]
        with self.assertRaises(ValueError):
            compare_baselines(rows, ResearchConfig(15, 20, 30))

    def test_nan_cost_fails(self):
        rows = [Sample("BTC", t, t + 1, t, (float(t),), .01)
                for t in (1, 3, 5, 11, 13, 15, 21, 23, 25)]
        with self.assertRaises(ValueError):
            compare_baselines(rows, ResearchConfig(10, 20, 30, fee_bps=float("nan")))

if __name__ == "__main__":
    unittest.main()
