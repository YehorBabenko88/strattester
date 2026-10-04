from .base import StrategyDefinition

class StrategyRegistry:
    def __init__(self): self._items={}
    def register(self,definition:StrategyDefinition):
        key=(definition.id,definition.version)
        if key in self._items: raise ValueError(f'duplicate strategy {key}')
        self._items[key]=definition
    def discover(self): return list(self._items.values())
    def set_enabled(self,strategy_id,version,enabled):
        old=self._items[(strategy_id,version)]
        self._items[(strategy_id,version)]=StrategyDefinition(old.id,old.version,old.requirements,old.implementation,enabled)


def builtin_registry():
    from .builtin.legacy_grid import LegacyGridStrategy
    r=StrategyRegistry()
    r.register(StrategyDefinition(
        LegacyGridStrategy.id,LegacyGridStrategy.version,
        LegacyGridStrategy.requirements,LegacyGridStrategy))
    from .builtin.research_adapter import hypothesis_definition
    from .builtin.research_levels import level_hypotheses
    from .builtin.research_smc import smc_hypotheses
    from .builtin.research_poc import poc_hypotheses
    from .builtin.research_volatility import volatility_hypotheses
    for spec in (*level_hypotheses(),*smc_hypotheses(),*poc_hypotheses(),*volatility_hypotheses()):
        r.register(hypothesis_definition(spec))
    return r
