from dataclasses import dataclass
from typing import Mapping,Any

@dataclass(frozen=True)
class HypothesisSpec:
    name:str
    family:str
    params:Mapping[str,Any]
    control:bool=False
