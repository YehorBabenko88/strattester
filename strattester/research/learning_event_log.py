"""Deterministic event log for scientific learning.

The log is the source of truth: unique decision/horizon events are replayed in
sequence order. Derived adaptive state may be rebuilt after a crash.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Sequence
import hashlib,json,math
from .decision_memory import ObservedOutcome,CounterfactualEstimate

@dataclass(frozen=True)
class LearningEvent:
    sequence:int
    event_id:str
    decision_id:str
    horizon:str
    utility:float
    timestamp_ms:int
    regime:str
    attribution:tuple[tuple[str,float],...]
    counterfactuals:tuple[CounterfactualEstimate,...]=()

def learning_event_id(outcome:ObservedOutcome)->str:
    raw=f"{outcome.decision_id}\0{outcome.horizon}".encode()
    return hashlib.sha256(raw).hexdigest()

class LearningEventLog:
    def __init__(self):
        self._events:dict[tuple[str,str],LearningEvent]={}
        self._next=1

    def append(self,outcome:ObservedOutcome,attribution:Mapping[str,float],*,regime:str,
               counterfactuals:Sequence[CounterfactualEstimate]=()):
        if not math.isfinite(outcome.utility):raise ValueError("non-finite utility")
        attrs=tuple(sorted((str(k),float(v)) for k,v in attribution.items()))
        if any(not math.isfinite(v) for _,v in attrs):raise ValueError("non-finite attribution")
        key=(outcome.decision_id,outcome.horizon)
        existing=self._events.get(key)
        candidate=(float(outcome.utility),int(outcome.timestamp_ms),str(regime),attrs,tuple(counterfactuals))
        if existing is not None:
            prior=(existing.utility,existing.timestamp_ms,existing.regime,existing.attribution,existing.counterfactuals)
            if prior!=candidate:raise ValueError("learning event collision")
            return existing,False
        e=LearningEvent(self._next,learning_event_id(outcome),outcome.decision_id,outcome.horizon,
                        float(outcome.utility),int(outcome.timestamp_ms),str(regime),attrs,tuple(counterfactuals))
        self._events[key]=e;self._next+=1
        return e,True

    def events(self,after_sequence=0):
        return tuple(sorted((e for e in self._events.values() if e.sequence>after_sequence),
                            key=lambda e:e.sequence))

    def export(self):
        return [{"sequence":e.sequence,"event_id":e.event_id,"decision_id":e.decision_id,
                 "horizon":e.horizon,"utility":e.utility,"timestamp_ms":e.timestamp_ms,
                 "regime":e.regime,"attribution":list(e.attribution)}
                for e in self.events()]
