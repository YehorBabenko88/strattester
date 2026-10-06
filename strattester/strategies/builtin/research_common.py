from dataclasses import dataclass
from typing import Mapping,Any,Callable

@dataclass(frozen=True)
class HypothesisSpec:
    name:str
    family:str
    params:Mapping[str,Any]
    control:bool=False
    execution_status:str="SPEC_ONLY"
    signal_generator:str|None=None
    def __post_init__(self):
        if self.execution_status not in ("SPEC_ONLY","EXECUTABLE"):
            raise ValueError("execution_status")
        if self.execution_status=="EXECUTABLE" and not self.signal_generator:
            raise ValueError("executable hypothesis requires signal_generator")

def executable_hypotheses(items):
    return tuple(x for x in items if x.execution_status=="EXECUTABLE")
