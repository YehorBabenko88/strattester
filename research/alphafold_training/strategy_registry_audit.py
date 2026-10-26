"""Read-only StrategyRegistry policy audit.

This deliberately does not invoke strategies or any execution adapter.
"""
from strattester.strategies.base import StrategyDefinition, strategy_fingerprint

def audit_registry(registry):
    definitions = registry.discover()
    seen = set()
    report = []
    for definition in definitions:
        if type(definition) is not StrategyDefinition:
            raise ValueError("invalid registry definition")
        key = (definition.id, definition.version)
        if (not isinstance(definition.id, str) or not definition.id.strip()
                or not isinstance(definition.version, str) or not definition.version.strip()
                or key in seen):
            raise ValueError("duplicate or invalid strategy identity")
        seen.add(key)
        if type(definition.enabled) is not bool:
            raise ValueError("nonboolean enablement")
        if "ALPHAFOLD" in definition.id.upper() and definition.enabled:
            raise ValueError("AlphaFold research must not be enabled by default")
        report.append({"id": definition.id, "version": definition.version,
                       "enabled": definition.enabled,
                       "fingerprint": strategy_fingerprint(definition)})
    return {"status": "AUDIT_ONLY", "count": len(report), "definitions": report}
