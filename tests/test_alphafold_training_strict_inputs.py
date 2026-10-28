"""Regression tests for research input fail-closed behavior."""
import unittest
from research.alphafold_training.evaluation import (
    Sample, validate, net_returns, fingerprint, bootstrap_mean_ci,
)

def sample(t, *, symbol="BTC"):
    return Sample(symbol, t, t + 1, t, (1.0,), 0.01)

class StrictInputsTests(unittest.TestCase):
    def test_nonfinite_costs_rejected(self):
        for fee in (float("nan"), float("inf"), -1.0, True):
            with self.subTest(fee=fee), self.assertRaises(ValueError):
                net_returns([sample(1)], [1], fee, 0)

    def test_unordered_execution_rejected(self):
        with self.assertRaises(ValueError):
            net_returns([sample(3), sample(1)], [1, 1], 1, 1)

    def test_boolean_position_rejected(self):
        with self.assertRaises(ValueError):
            net_returns([sample(1)], [True], 1, 1)

    def test_invalid_time_and_instrument(self):
        for s in (
            Sample("", 1, 2, 1, (1.,), .01),
            Sample("BTC", True, 2, 1, (1.,), .01),
            Sample("BTC", 1.5, 2, 1, (1.,), .01),
        ):
            with self.subTest(sample=s), self.assertRaises(ValueError):
                validate([s])

    def test_uncanonical_hash_rejected(self):
        with self.assertRaises(TypeError):
            fingerprint({"object": object()})

    def test_nonfinite_bootstrap_rejected(self):
        for x in (float("nan"), float("inf"), True):
            with self.subTest(x=x), self.assertRaises(ValueError):
                bootstrap_mean_ci([0., x], repetitions=5)

if __name__ == "__main__":
    unittest.main()
