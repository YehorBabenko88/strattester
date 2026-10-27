import hashlib
import hmac
import unittest
from strattester.research.financial_evaluation import Trade
from research.alphafold_training.authenticated_funding import FundingRecord, canonical_funding
from research.alphafold_training.authenticated_reconciliation import reconcile_authenticated

class AuthenticatedReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [FundingRecord("SOL", 15, 16, .001)]
        self.key = b"k" * 32
        self.args = dict(producer="trusted-producer", epoch="epoch-1", dataset_version="v1")
        self.mac = hmac.new(self.key, canonical_funding(self.rows, **self.args), hashlib.sha256).hexdigest()

    def run_reconcile(self, rows=None, **overrides):
        args = dict(self.args, trusted_key=self.key, expected_mac=self.mac,
                    coverage_start_ns=0, coverage_end_ns=30)
        args.update(overrides)
        return reconcile_authenticated([Trade("SOL", 10, 20, .01, 1)],
                                       self.rows if rows is None else rows, **args)

    def test_authentication_does_not_imply_completeness(self):
        result = self.run_reconcile()
        self.assertTrue(result["funding_authenticated"])
        self.assertFalse(result["coverage_completeness_verified"])
        self.assertFalse(result["real_oos_authorized"])
        self.assertAlmostEqual(result["net_returns"][0], .009)

    def test_tampering_rejected(self):
        with self.assertRaises(ValueError):
            self.run_reconcile([FundingRecord("SOL", 15, 16, -.001)])

    def test_out_of_coverage_rejected(self):
        with self.assertRaises(ValueError):
            self.run_reconcile(coverage_end_ns=19)

if __name__ == "__main__":
    unittest.main()
