import unittest
from research.alphafold_training.cost_sensitivity import cost_sensitivity
from research.alphafold_training.evaluation import Sample

class CostSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.rows = [Sample("BTC", t, t + 1, t, (1.,), .01) for t in (1, 3, 5)]

    def test_costs_monotonically_reduce_fixed_signal_pnl(self):
        result = cost_sensitivity(self.rows, [1, 1, -1], [(0, 0), (10, 5), (30, 20)])
        values = [s["mean_net_return"] for s in result["scenarios"]]
        self.assertGreater(values[0], values[1])
        self.assertGreater(values[1], values[2])
        self.assertTrue(result["positions_frozen"])

    def test_nan_and_negative_cost_rejected(self):
        for scenario in ((float("nan"), 0), (-1, 0), (0, float("inf")), (True, 0)):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                cost_sensitivity(self.rows, [1, 1, -1], [scenario])

    def test_reject_unordered_observations(self):
        with self.assertRaises(ValueError):
            cost_sensitivity(list(reversed(self.rows)), [1, 1, -1], [(1, 1)])

if __name__ == "__main__":
    unittest.main()
