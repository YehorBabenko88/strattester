"""Offline research strategy configuration and explicit no-live authorization boundary.

This module does not register an executable strategy or accept exchange clients.
"""
from dataclasses import dataclass
from strattester.research.financial_contract import Instrument, integer, digest

@dataclass(frozen=True)
class FinancialResearchSpec:
    universe: tuple[Instrument, ...]
    timeframe_ns: int
    forecast_horizon_ns: int
    model_version: str
    max_samples: int = 1024
    max_folds: int = 32
    enabled: bool = False
    mode: str = "OFFLINE_RESEARCH_ONLY"

    def validate(self):
        if type(self.enabled) is not bool or self.enabled:
            raise ValueError("financial research must remain disabled by default")
        if self.mode != "OFFLINE_RESEARCH_ONLY":
            raise ValueError("live execution forbidden")
        if not self.universe or type(self.universe) is not tuple:
            raise ValueError("explicit universe required")
        if any(type(instrument) is not Instrument for instrument in self.universe):
            raise ValueError("invalid instrument")
        if len(set(self.universe)) != len(self.universe):
            raise ValueError("duplicate instruments")
        for instrument in self.universe:
            if type(instrument) is not Instrument:
                raise ValueError("invalid instrument")
            instrument.validate()
        integer(self.timeframe_ns, "timeframe", 1)
        integer(self.forecast_horizon_ns, "forecast horizon", 1)
        integer(self.max_samples, "max_samples", 1)
        integer(self.max_folds, "max_folds", 1)
        if len(self.universe) > self.max_samples:
            raise ValueError("universe exceeds sample budget")
        if len(self.universe) > 64:
            raise ValueError("universe exceeds structural track admission limit")
        if self.forecast_horizon_ns % self.timeframe_ns:
            raise ValueError("forecast horizon must align to timeframe")
        if self.max_samples > 1024 or self.max_folds > 32:
            raise ValueError("research resource budget")
        if not isinstance(self.model_version, str) or not self.model_version.strip():
            raise ValueError("model version required")
        return self
