"""Offline contract tests for research evaluation primitives."""
import unittest
from research.alphafold_training.evaluation import (
    Sample, purged_split, net_returns, fingerprint, bootstrap_mean_ci,
    negative_control, registry_record,
)

class EvaluationTests(unittest.TestCase):
    def test_purge_label_overlap(self):
        rows = [
            Sample("BTC", 1, 11, 1, (1.,), .01),
            Sample("BTC", 12, 14, 12, (2.,), .02),
            Sample("BTC", 21, 23, 21, (3.,), .03),
        ]
        train, validation, test = purged_split(rows, 10, 20, 30)
        self.assertEqual([len(x) for x in (train, validation, test)], [0, 1, 1])

    def test_future_feature_rejected(self):
        with self.assertRaises(ValueError):
            purged_split([Sample("BTC", 1, 2, 3, (1.,), .1)], 4, 6, 8)

    def test_costs_and_turnover(self):
        rows = [Sample("BTC", i, i+1, i, (1.,), .01) for i in (1, 2)]
        self.assertAlmostEqual(net_returns(rows, [1, 1], 10, 5)[0], .0085)
        self.assertAlmostEqual(net_returns(rows, [1, 1], 10, 5)[1], .01)

    def test_determinism(self):
        self.assertEqual(fingerprint({"b": 1, "a": 2}), fingerprint({"a": 2, "b": 1}))
        self.assertEqual(bootstrap_mean_ci([1., 2., 3.], seed=7),
                         bootstrap_mean_ci([1., 2., 3.], seed=7))
        self.assertEqual(negative_control([1, -1, 0, 1], 9),
                         negative_control([1, -1, 0, 1], 9))

    def test_registry_fail_closed(self):
        with self.assertRaises(ValueError):
            registry_record(dataset_sha256="bad", model_sha256="0"*64, config={}, metrics={})

if __name__ == "__main__":
    unittest.main()
