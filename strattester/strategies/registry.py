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
        self._items[(strategy_id,version)]=StrategyDefinition(old.id,old.version,old.requirements,old.implementation,enabled,old.feature_versions)
