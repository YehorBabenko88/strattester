from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Iterable

@dataclass(frozen=True,order=True)
class CausalFeature:
    event_time:int
    known_at:int
    kind:str
    value:Any
    version:str
    def __post_init__(self):
        if self.known_at < self.event_time:
            raise ValueError('known_at cannot precede event_time')

class CausalView:
    def __init__(self,features:Iterable[CausalFeature]):
        self._features=tuple(features)
    def at(self,decision_time:int)->tuple[CausalFeature,...]:
        return tuple(sorted((x for x in self._features if x.known_at<=decision_time),key=lambda x:(x.known_at,x.event_time,x.kind)))
