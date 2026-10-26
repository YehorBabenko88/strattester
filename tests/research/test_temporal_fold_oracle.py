import unittest
from research.alphafold_training.temporal_fold_oracle import LabelInterval, validate_folds

def row(symbol, start, end, tf=60):
    return LabelInterval(symbol, tf, start, end)

class TemporalFoldOracleTests(unittest.TestCase):
    def test_disjoint_fold(self):
        self.assertEqual(validate_folds([([row("BTC", 1, 3)], [row("ETH", 4, 6)],
                                          [row("SOL", 7, 9)])])["fold_count"], 1)

    def test_cross_instrument_label_overlap(self):
        with self.assertRaises(ValueError):
            validate_folds([([row("BTC", 1, 10)], [row("ETH", 9, 12)],
                             [row("SOL", 13, 15)])])

    def test_prior_oos_reuse_requires_explicit_mode(self):
        folds = [
            ([row("BTC", 1, 2)], [row("BTC", 3, 4)], [row("SOL", 5, 7)]),
            ([row("BTC", 1, 2), row("ETH", 6, 7)],
             [row("BTC", 8, 9)], [row("SOL", 10, 12)]),
        ]
        with self.assertRaises(ValueError):
            validate_folds(folds)
        self.assertTrue(validate_folds(folds, allow_prior_oos_retraining=True)["sequential_retraining"])

    def test_overlapping_oos_rejected_even_in_sequential_mode(self):
        folds = [
            ([row("BTC", 1, 2)], [row("BTC", 3, 4)], [row("SOL", 5, 9)]),
            ([row("BTC", 1, 2)], [row("BTC", 4, 5)], [row("ETH", 8, 10)]),
        ]
        with self.assertRaises(ValueError):
            validate_folds(folds, allow_prior_oos_retraining=True)

if __name__ == "__main__":
    unittest.main()
