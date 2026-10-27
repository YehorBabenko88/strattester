import hashlib
import hmac
import json
import unittest
from research.alphafold_training.funding_coverage_manifest import verify_coverage_manifest

class CoverageManifestTests(unittest.TestCase):
    def setUp(self):
        self.key = b"m" * 32
        self.digest = "a" * 64
        self.manifest = {
            "schema": "funding.coverage.v1", "producer": "trusted-producer",
            "epoch": "epoch-1", "dataset_version": "v1",
            "funding_sha256": self.digest, "coverage_start_ns": 0,
            "coverage_end_ns": 100, "instruments": ["SOL"], "complete": True,
        }

    def mac(self, manifest=None):
        payload = json.dumps(self.manifest if manifest is None else manifest,
                             sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self.key, payload, hashlib.sha256).hexdigest()

    def test_valid_manifest(self):
        result = verify_coverage_manifest(self.manifest, trusted_key=self.key,
                                          expected_mac=self.mac(), funding_sha256=self.digest)
        self.assertEqual(result["status"], "AUTHENTICATED_PRODUCER_ASSERTION")

    def test_incomplete_manifest_rejected(self):
        manifest = dict(self.manifest, complete=False)
        with self.assertRaises(ValueError):
            verify_coverage_manifest(manifest, trusted_key=self.key,
                                     expected_mac=self.mac(manifest), funding_sha256=self.digest)

    def test_tampered_coverage_rejected(self):
        manifest = dict(self.manifest, coverage_end_ns=200)
        with self.assertRaises(ValueError):
            verify_coverage_manifest(manifest, trusted_key=self.key,
                                     expected_mac=self.mac(), funding_sha256=self.digest)

    def test_wrong_funding_digest_rejected(self):
        with self.assertRaises(ValueError):
            verify_coverage_manifest(self.manifest, trusted_key=self.key,
                                     expected_mac=self.mac(), funding_sha256="b"*64)

if __name__ == "__main__":
    unittest.main()
