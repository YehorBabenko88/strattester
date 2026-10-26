import unittest
from physical_g1_stop_matrix import REQUIRED, evaluate_physical_g1


class StopMatrixTests(unittest.TestCase):
    def test_missing_evidence_blocks(self):
        result = evaluate_physical_g1({})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("owner_signature", result["stop"])

    def test_self_attested_all_green_cannot_authorize(self):
        forged = {key: "INDEPENDENT_VERIFIED" for key in REQUIRED}
        result = evaluate_physical_g1(forged)
        self.assertFalse(result["physical_g1_authorized"])
        self.assertIn("external_authority_and_signed_plan_not_verified_by_this_module", result["stop"])

    def test_owner_plan_substitution_blocks(self):
        forged = {key: "INDEPENDENT_VERIFIED" for key in REQUIRED}
        forged["owner_plan_nonce"] = "SUBSTITUTED"
        self.assertIn("owner_plan_nonce", evaluate_physical_g1(forged)["stop"])

    def test_network_gap_blocks(self):
        forged = {key: "INDEPENDENT_VERIFIED" for key in REQUIRED}
        forged["network_ipv4_ipv6_dns_udp_loopback"] = "NOT_RUN"
        self.assertIn("network_ipv4_ipv6_dns_udp_loopback", evaluate_physical_g1(forged)["stop"])

    def test_extra_evidence_key_blocks(self):
        forged = {key: "INDEPENDENT_VERIFIED" for key in REQUIRED}
        forged["override"] = "PASS"
        self.assertIn("override", evaluate_physical_g1(forged)["stop"])


if __name__ == "__main__":
    unittest.main()
