import math
import unittest
from strattester.research.financial_evaluation import Trade, evaluate_ledger, gaussian_scores
from research.alphafold_training.system_audit_oracles import oracle_ledger, oracle_gaussian_nll

class SystemAuditOracles(unittest.TestCase):
    def test_differential_roundtrip_costs(self):
        for position in (-1, 0, 1):
            for fee, slip, funding in ((0, 0, 0), (7, 3, 2), (20, 15, 50)):
                with self.subTest(position=position, fee=fee, slip=slip, funding=funding):
                    trades = [Trade("SOLUSDT", 10, 20, .015, position)]
                    observed = evaluate_ledger(trades, fee_bps=fee, slippage_bps=slip, funding_bps=funding)
                    expected = oracle_ledger(trades, fee, slip, funding)
                    self.assertAlmostEqual(observed["returns"][0], expected["returns"][0])
                    self.assertEqual(observed["turnover"], expected["turnover"])

    def test_cross_instrument_and_terminal_liquidation(self):
        trades = [Trade("BTC", 10, 20, .01, 1), Trade("SOL", 11, 19, -.02, -1)]
        observed = evaluate_ledger(trades, fee_bps=10, slippage_bps=5)
        expected = oracle_ledger(trades, 10, 5)
        self.assertEqual(observed["turnover"], 4)
        self.assertEqual(observed["returns"], expected["returns"])

    def test_gaussian_nll_reference(self):
        for mu, sigma, y in ((0., 1., 0.), (.01, .5, -.2), (-.1, 2., .3)):
            with self.subTest(mu=mu, sigma=sigma, y=y):
                observed = gaussian_scores([mu], [sigma], [y])
                self.assertAlmostEqual(observed["nll"], oracle_gaussian_nll(mu, sigma, y))

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_ledger([Trade("SOL", 10, 20, .01, 1), Trade("SOL", 19, 21, .02, -1)])

    def test_invalid_nonfinite_cost_rejected(self):
        for cost in (float("nan"), float("inf"), -1):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                evaluate_ledger([Trade("SOL", 10, 20, .01, 1)], funding_bps=cost)

if __name__ == "__main__":
    unittest.main()
