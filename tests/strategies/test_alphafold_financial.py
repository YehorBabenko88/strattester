import unittest
from strattester.strategies.registry import StrategyRegistry
from strattester.strategies.builtin.alphafold_financial import (
    AlphaFoldFinancialResearch, alphafold_financial_definition,
)

class FinancialStrategyRegistrationTests(unittest.TestCase):
    def test_distinct_disabled_definition(self):
        definition = alphafold_financial_definition()
        self.assertFalse(definition.enabled)
        self.assertEqual(definition.id, "ALPHAFOLD_FINANCIAL_RESEARCH")
        registry = StrategyRegistry()
        registry.register(definition)
        self.assertEqual(len(registry.discover()), 1)

    def test_legacy_context_fails_closed(self):
        class DummyContext:
            symbol = "SOLUSDT"
            def candles(self, timeframe):
                raise AssertionError("must not consume unverified candles")
        for checkpoint in (None, "untrusted.pkl"):
            with self.subTest(checkpoint=checkpoint), self.assertRaises((RuntimeError, ValueError)):
                AlphaFoldFinancialResearch().run_context(DummyContext(), checkpoint)

if __name__ == "__main__":
    unittest.main()
