import unittest
from research.alphafold_training.authenticated_funding import FundingRecord
from research.alphafold_training.funding_schedule_oracle import check_funding_schedule

def event(t):
    return FundingRecord("SOL", t, t, .001)

class FundingScheduleTests(unittest.TestCase):
    def test_complete_grid(self):
        result = check_funding_schedule([event(10), event(20), event(30)],
                                        instrument="SOL", start_ns=0, end_ns=30,
                                        cadence_ns=10, first_event_ns=10)
        self.assertEqual(result["expected_count"], 3)
        self.assertFalse(result["exchange_truth_verified"])

    def test_missing_event_rejected(self):
        with self.assertRaises(ValueError):
            check_funding_schedule([event(10), event(30)], instrument="SOL",
                                   start_ns=0, end_ns=30, cadence_ns=10, first_event_ns=10)

    def test_duplicate_event_rejected(self):
        with self.assertRaises(ValueError):
            check_funding_schedule([event(10), event(10), event(20), event(30)],
                                   instrument="SOL", start_ns=0, end_ns=30,
                                   cadence_ns=10, first_event_ns=10)

    def test_resource_limit(self):
        with self.assertRaises(ValueError):
            check_funding_schedule([], instrument="SOL", start_ns=0,
                                   end_ns=1000000, cadence_ns=1,
                                   first_event_ns=0, max_expected=100)

if __name__ == "__main__":
    unittest.main()
