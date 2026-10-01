from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Protocol

@dataclass(frozen=True)
class DataRequirement:
    dataset:str
    timeframes:tuple[str,...]=()
    required:bool=True

@dataclass(frozen=True)
class StrategyDefinition:
    id:str
    version:str
    requirements:tuple[DataRequirement,...]
    implementation:type
    enabled:bool=True

def strategy_fingerprint(d:StrategyDefinition)->str:
    payload={'id':d.id,'version':d.version,'requirements':[(r.dataset,r.timeframes,r.required) for r in d.requirements],'impl':f'{d.implementation.__module__}.{d.implementation.__qualname__}'}
    return sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

class Strategy(Protocol):
    id:str
    version:str
    requirements:tuple[DataRequirement,...]
    def run(self,candles,checkpoint=None): ...
