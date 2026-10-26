import unittest
from strattester.research.financial_evaluation import Trade
from research.alphafold_training.funding_event_oracle import FundingEvent
from research.alphafold_training.funding_reconciliation import reconcile_funding

class FundingReconciliationTests(unittest.TestCase):
    def test_signed_events_change_long_and_short_differently(self):
        trades = [Trade("SOL", 10, 20, .01, 1), Trade("BTC", 10, 20, .01, -1)]
        events = [FundingEvent("SOL", 15, .002), FundingEvent("BTC", 15, .002)]
        result = reconcile_funding(trades, events)
        self.assertEqual(result["funding_cashflows"], [.002, -.002])
        self.assertFalse(result["portfolio_pnl_authorized"])
        self.assertFalse(result["provenance_verified"])

    def test_no_events_same_as_no_funding(self):
        result = reconcile_funding([Trade("SOL", 10, 20, .01, 1)], [], fee_bps=10)
        self.assertAlmostEqual(result["net_returns"][0], .008)

    def test_duplicate_unused_funding_rejected(self):
        event = FundingEvent("ETH", 100, .001)
        with self.assertRaises(ValueError):
            reconcile_funding([Trade("SOL", 10, 20, .01, 1)], [event, event])

    def test_duplicate_funding_rejected(self):
        event = FundingEvent("SOL", 15, .001)
        with self.assertRaises(ValueError):
            reconcile_funding([Trade("SOL", 10, 20, .01, 1)], [event, event])

if __name__ == "__main__":
    unittest.main()
