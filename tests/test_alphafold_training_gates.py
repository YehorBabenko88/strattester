import unittest
from research.alphafold_training.evaluation import Sample
from research.alphafold_training.gates import (
    assert_no_cross_partition_label_overlap, assert_feature_schema,
    assert_prediction_contract, assert_disjoint_windows,
)

def row(symbol, start, end, features=(1.,)):
    return Sample(symbol, start, end, start, features, .01)

class ResearchGatesTests(unittest.TestCase):
    def test_global_cross_instrument_leakage(self):
        with self.assertRaises(ValueError):
            assert_no_cross_partition_label_overlap(
                [row("BTC", 1, 15)], [row("ETH", 12, 18)], [row("ETH", 21, 22)])

    def test_schema_drift(self):
        with self.assertRaises(ValueError):
            assert_feature_schema([row("BTC", 1, 2), row("ETH", 3, 4, (1., 2.))])

    def test_invalid_prediction_types(self):
        for invalid in (float("nan"), float("inf"), "1", True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    assert_prediction_contract([invalid], [row("BTC", 1, 2)])

    def test_repeated_oos_rejected(self):
        fold = ([row("BTC", 1, 2)], [row("BTC", 3, 4)], [row("BTC", 5, 6)])
        with self.assertRaises(ValueError):
            assert_disjoint_windows([fold, fold])

if __name__ == "__main__":
    unittest.main()
