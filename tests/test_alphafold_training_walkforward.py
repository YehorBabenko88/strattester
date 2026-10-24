import unittest
from research.alphafold_training.evaluation import Sample
from research.alphafold_training.runner import ResearchConfig
from research.alphafold_training.walkforward import compare_walk_forward

class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.rows = [Sample("BTC", t, t + 1, t, (float(t),), .001)
                     for t in (1, 3, 5, 11, 13, 15, 21, 23, 25, 31, 33, 35)]

    def test_two_disjoint_oos_folds(self):
        configs = [ResearchConfig(10, 20, 30), ResearchConfig(20, 30, 40)]
        result = compare_walk_forward(self.rows, configs, allow_retraining_on_prior_oos=True)
        self.assertEqual(result["fold_count"], 2)
        self.assertEqual(result["fold_independence"], "SEQUENTIAL_RETRAINING")
        self.assertEqual(result["aggregation"], "NOT_AUTHORIZED_WITHOUT_PORTFOLIO_LEDGER")

    def test_prior_oos_reuse_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            compare_walk_forward(self.rows, [ResearchConfig(10, 20, 30), ResearchConfig(20, 30, 40)])

    def test_duplicate_test_period_rejected(self):
        with self.assertRaises(ValueError):
            compare_walk_forward(self.rows, [ResearchConfig(10, 20, 30)] * 2)

    def test_empty_folds_rejected(self):
        with self.assertRaises(ValueError):
            compare_walk_forward(self.rows, [])

if __name__ == "__main__":
    unittest.main()
