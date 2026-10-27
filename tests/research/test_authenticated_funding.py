import hashlib
import hmac
import unittest
from research.alphafold_training.authenticated_funding import (
    FundingRecord, canonical_funding, verify_funding,
)

class AuthenticatedFundingTests(unittest.TestCase):
    def setUp(self):
        self.key = b"k" * 32
        self.rows = [FundingRecord("SOLUSDT", 100, 105, .001)]
        self.args = dict(producer="trusted-producer", epoch="epoch-1", dataset_version="v1")

    def sign(self, rows=None):
        data = canonical_funding(self.rows if rows is None else rows, **self.args)
        return hmac.new(self.key, data, hashlib.sha256).hexdigest()

    def test_valid_external_key(self):
        result = verify_funding(iter(self.rows), **self.args,
                                trusted_key=self.key, expected_mac=self.sign())
        self.assertEqual(result["count"], 1)

    def test_tampered_rate_rejected(self):
        tampered = [FundingRecord("SOLUSDT", 100, 105, -.001)]
        with self.assertRaises(ValueError):
            verify_funding(tampered, **self.args, trusted_key=self.key,
                           expected_mac=self.sign())

    def test_wrong_key_rejected(self):
        with self.assertRaises(ValueError):
            verify_funding(self.rows, **self.args, trusted_key=b"x"*32,
                           expected_mac=self.sign())

    def test_duplicate_and_future_invalid(self):
        with self.assertRaises(ValueError):
            canonical_funding(self.rows + self.rows, **self.args)
        with self.assertRaises(ValueError):
            canonical_funding([FundingRecord("SOLUSDT", 100, 99, .01)], **self.args)

if __name__ == "__main__":
    unittest.main()
