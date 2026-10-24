"""Explicit disabled-by-default structural research strategy adapter.

No training, checkpoint loading, network or trading is reachable through the
ordinary StrategyContext candle API. Typed producer-verified snapshots are
required by the separate financial research pipeline.
"""
from strattester.strategies.base import StrategyDefinition, DataRequirement

class AlphaFoldFinancialResearch:
    id = "ALPHAFOLD_FINANCIAL_RESEARCH"
    version = "0.1.0"
    requirements = (DataRequirement("candles", ("1m",)),)

    def run_context(self, context, checkpoint=None):
        if checkpoint is not None:
            raise ValueError("ordinary strategy context cannot load financial model checkpoints")
        # This adapter intentionally refuses unverified legacy candle records.
        # Financial structural inference requires Snapshot with producer
        # provenance, availability, watermark and revision contracts.
        raise RuntimeError("BLOCKED: verified financial Snapshot required; legacy candle context is insufficient")

def alphafold_financial_definition():
    return StrategyDefinition(
        id=AlphaFoldFinancialResearch.id,
        version=AlphaFoldFinancialResearch.version,
        requirements=AlphaFoldFinancialResearch.requirements,
        implementation=AlphaFoldFinancialResearch,
        enabled=False,
        feature_versions=("financial_structural_v1",),
    )
