import hashlib
import hmac
import json
import unittest
from strattester.research.financial_evaluation import Trade
from research.alphafold_training.authenticated_funding import FundingRecord, canonical_funding
from research.alphafold_training.manifest_bound_reconciliation import reconcile_with_manifest

class ManifestBoundReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [FundingRecord("SOL", 15, 16, .001)]
        self.funding_key = b"f" * 32
        self.manifest_key = b"m" * 32
        self.manifest = {
            "schema": "funding.coverage.v1", "producer": "producer",
            "epoch": "epoch", "dataset_version": "v1",
            "funding_sha256": hashlib.sha256(canonical_funding(
                self.rows, producer="producer", epoch="epoch", dataset_version="v1")).hexdigest(),
            "coverage_start_ns": 0, "coverage_end_ns": 30,
            "instruments": ["SOL"], "complete": True,
        }

    def sign(self):
        fbytes = canonical_funding(self.rows, producer="producer", epoch="epoch", dataset_version="v1")
        mbytes = json.dumps(self.manifest, sort_keys=True, separators=(",", ":")).encode()
        return dict(funding_key=self.funding_key,
                    funding_mac=hmac.new(self.funding_key, fbytes, hashlib.sha256).hexdigest(),
                    manifest_key=self.manifest_key,
                    manifest_mac=hmac.new(self.manifest_key, mbytes, hashlib.sha256).hexdigest())

    def test_verified_both_but_real_oos_blocked(self):
        result = reconcile_with_manifest([Trade("SOL", 10, 20, .01, 1)],
                                         self.rows, self.manifest, **self.sign())
        self.assertTrue(result["coverage_producer_assertion_authenticated"])
        self.assertFalse(result["real_oos_authorized"])
        self.assertFalse(result["coverage_completeness_verified"])

    def test_wrong_instrument_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_with_manifest([Trade("BTC", 10, 20, .01, 1)],
                                    self.rows, self.manifest, **self.sign())

    def test_tampered_manifest_rejected(self):
        tampered = dict(self.manifest, coverage_end_ns=100)
        with self.assertRaises(ValueError):
            reconcile_with_manifest([Trade("SOL", 10, 20, .01, 1)],
                                    self.rows, tampered, **self.sign())

if __name__ == "__main__":
    unittest.main()
