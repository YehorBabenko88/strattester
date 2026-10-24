import unittest
from strattester.research.financial_contract import Instrument
from strattester.research.financial_research_spec import FinancialResearchSpec

class FinancialResearchSpecTests(unittest.TestCase):
    def setUp(self):
        self.btc = Instrument("bybit", "linear", "BTCUSDT")
        self.alt = Instrument("bybit", "linear", "SOLUSDT")

    def test_any_explicit_instrument(self):
        spec = FinancialResearchSpec((self.btc, self.alt), 60_000_000_000,
                                     300_000_000_000, "financial-structural-v1")
        self.assertIs(spec.validate(), spec)

    def test_live_mode_rejected(self):
        for overrides in ({"mode": "LIVE"}, {"enabled": True}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                FinancialResearchSpec((self.alt,), 60, 300, "v1", **overrides).validate()

    def test_unhashable_universe_element_fails_closed(self):
        with self.assertRaises(ValueError):
            FinancialResearchSpec(([],), 60, 300, "v1").validate()

    def test_duplicate_universe_rejected(self):
        with self.assertRaises(ValueError):
            FinancialResearchSpec((self.alt, self.alt), 60, 300, "v1").validate()

    def test_structural_track_limit(self):
        instruments = tuple(Instrument("bybit", "linear", f"COIN{i}USDT") for i in range(65))
        with self.assertRaises(ValueError):
            FinancialResearchSpec(instruments, 60, 300, "v1").validate()

    def test_universe_exceeds_sample_budget(self):
        with self.assertRaises(ValueError):
            FinancialResearchSpec((self.btc, self.alt), 60, 300, "v1", max_samples=1).validate()

    def test_horizon_alignment_rejected(self):
        with self.assertRaises(ValueError):
            FinancialResearchSpec((self.alt,), 60, 301, "v1").validate()

if __name__ == "__main__":
    unittest.main()
