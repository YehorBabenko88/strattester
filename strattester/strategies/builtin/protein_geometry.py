"""Opt-in geometry research strategy for any instrument with complete candles."""
from __future__ import annotations
from strattester.strategies.base import StrategyDefinition, DataRequirement
from strattester.research.protein_geometry import market_backbone


class ProteinGeometryResearch:
    id = "PROTEIN_GEOMETRY_RESEARCH"
    version = "0.1.0"
    requirements = (DataRequirement("candles", ("1m",)),)

    def run_context(self, context, checkpoint=None):
        rows = list(context.candles("1m"))
        if len(rows) < 17:
            return {"status": "INSUFFICIENT_HISTORY", "symbol": context.symbol,
                    "points": [], "trades": [], "mode": "OFFLINE_RESEARCH_ONLY"}
        times = [int(c.open_time) for c in rows]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("candle timestamps must increase strictly")
        points = market_backbone([c.close for c in rows], window=16)
        return {"status": "FEATURES_ONLY", "symbol": context.symbol,
                "timestamps": times[16:], "points": [list(p) for p in points],
                "trades": [], "mode": "OFFLINE_RESEARCH_ONLY"}


def protein_geometry_definition():
    return StrategyDefinition(
        id=ProteinGeometryResearch.id,
        version=ProteinGeometryResearch.version,
        requirements=ProteinGeometryResearch.requirements,
        implementation=ProteinGeometryResearch,
        enabled=False,
        feature_versions=("protein_geometry_v1",),
    )
