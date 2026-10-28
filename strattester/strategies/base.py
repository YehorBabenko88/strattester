from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import inspect
from typing import Protocol
from strattester.marketdata.datasets import DatasetKind

@dataclass(frozen=True)
class DataRequirement:
    dataset:DatasetKind|str
    timeframes:tuple[str,...]=()
    required:bool=True
    min_observations:int=1
    lookback_ms:int|None=None
    def __post_init__(self):
        if isinstance(self.dataset,str):
            object.__setattr__(self,'dataset',DatasetKind(self.dataset))
        if not isinstance(self.dataset,DatasetKind) or type(self.timeframes) is not tuple or any(type(tf) is not str for tf in self.timeframes):
            raise ValueError('invalid dataset/timeframes contract')
        if type(self.required) is not bool or type(self.min_observations) is not int or self.min_observations<1:
            raise ValueError('invalid requirement minimum/required flag')
        if self.lookback_ms is not None and (type(self.lookback_ms) is not int or self.lookback_ms<1):
            raise ValueError('invalid requirement lookback')

@dataclass(frozen=True)
class StrategyDefinition:
    id:str
    version:str
    requirements:tuple[DataRequirement,...]
    implementation:type
    enabled:bool=True
    feature_versions:tuple[str,...]=()

def strategy_fingerprint(d:StrategyDefinition)->str:
    try:
        source=inspect.getsource(d.implementation)
    except (OSError,TypeError):
        source=f'{d.implementation.__module__}.{d.implementation.__qualname__}'
    payload={'id':d.id,'version':d.version,'requirements':[(r.dataset.value,r.timeframes,r.required,r.min_observations,r.lookback_ms) for r in d.requirements],'impl':f'{d.implementation.__module__}.{d.implementation.__qualname__}','source_sha256':sha256(source.encode()).hexdigest(),'feature_versions':d.feature_versions}
    return sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

class Strategy(Protocol):
    id:str
    version:str
    requirements:tuple[DataRequirement,...]
    def run(self,candles,checkpoint=None): ...
