import unittest
from strattester.strategies.base import StrategyDefinition
from strattester.strategies.registry import StrategyRegistry
from research.alphafold_training.strategy_registry_audit import audit_registry

class AlphaFoldStub:
    pass

class RegistryAuditTests(unittest.TestCase):
    def test_disabled_alphafold_accepted(self):
        registry = StrategyRegistry()
        registry.register(StrategyDefinition("ALPHAFOLD_FINANCIAL", "v1", (), AlphaFoldStub, False))
        result = audit_registry(registry)
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["definitions"][0]["enabled"])

    def test_enabled_alphafold_rejected(self):
        registry = StrategyRegistry()
        registry.register(StrategyDefinition("ALPHAFOLD_FINANCIAL", "v1", (), AlphaFoldStub, True))
        with self.assertRaises(ValueError):
            audit_registry(registry)

    def test_duplicate_registry_registration_rejected(self):
        registry = StrategyRegistry()
        definition = StrategyDefinition("EXPERIMENT", "v1", (), AlphaFoldStub, False)
        registry.register(definition)
        with self.assertRaises(ValueError):
            registry.register(definition)

if __name__ == "__main__":
    unittest.main()
