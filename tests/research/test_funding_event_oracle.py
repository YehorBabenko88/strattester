import unittest
from research.alphafold_training.funding_event_oracle import FundingEvent, funding_cashflow

class FundingEventOracleTests(unittest.TestCase):
    def test_long_pays_short_receives(self):
        events = [FundingEvent("SOL", 20, .001), FundingEvent("SOL", 30, -.002)]
        self.assertAlmostEqual(funding_cashflow(1, 10, 30, "SOL", events), .001)
        self.assertAlmostEqual(funding_cashflow(-1, 10, 30, "SOL", events), -.001)

    def test_other_instrument_excluded(self):
        events = [FundingEvent("BTC", 20, .01)]
        self.assertEqual(funding_cashflow(1, 10, 30, "SOL", events), 0)

    def test_entry_excluded_exit_included(self):
        events = [FundingEvent("SOL", 10, .01), FundingEvent("SOL", 30, .002)]
        self.assertAlmostEqual(funding_cashflow(1, 10, 30, "SOL", events), -.002)

    def test_duplicate_event_rejected(self):
        event = FundingEvent("SOL", 20, .001)
        with self.assertRaises(ValueError):
            funding_cashflow(1, 10, 30, "SOL", [event, event])

    def test_nonfinite_rate_rejected(self):
        with self.assertRaises(ValueError):
            funding_cashflow(1, 10, 30, "SOL", [FundingEvent("SOL", 20, float("nan"))])

if __name__ == "__main__":
    unittest.main()
