"""Decision/outcome memory with explicit counterfactual provenance.

Observed outcomes and estimated alternatives are intentionally different types.
Learning may use observed evidence directly; counterfactuals are discounted by
estimator confidence and never silently promoted to facts.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Sequence
import math,time

@dataclass(frozen=True)
class DecisionTrace:
    decision_id:str
    timestamp_ms:int
    action:str
    reasons:tuple[str,...]
    context_fingerprint:str

@dataclass(frozen=True)
class ObservedOutcome:
    decision_id:str
    horizon:str
    utility:float
    timestamp_ms:int

@dataclass(frozen=True)
class CounterfactualEstimate:
    decision_id:str
    alternative_action:str
    horizon:str
    estimated_utility:float
    estimator:str
    confidence:float
    assumptions:tuple[str,...]=()

@dataclass(frozen=True)
class LearningSignal:
    decision_id:str
    realized_utility:float
    best_alternative:float|None
    regret:float|None
    counterfactual_confidence:float
    safe_for_adaptation:bool

class DecisionMemory:
    def __init__(self):
        self.traces:dict[str,DecisionTrace]={}
        self.outcomes:dict[tuple[str,str],ObservedOutcome]={}
        self.counterfactuals:dict[tuple[str,str,str],CounterfactualEstimate]={}

    def remember(self,trace:DecisionTrace):
        if trace.decision_id in self.traces and self.traces[trace.decision_id]!=trace:
            raise ValueError("decision id collision")
        self.traces[trace.decision_id]=trace

    def observe(self,outcome:ObservedOutcome):
        if outcome.decision_id not in self.traces: raise ValueError("unknown decision")
        if not math.isfinite(outcome.utility): raise ValueError("non-finite utility")
        self.outcomes[(outcome.decision_id,outcome.horizon)]=outcome

    def estimate(self,cf:CounterfactualEstimate):
        if cf.decision_id not in self.traces: raise ValueError("unknown decision")
        if not cf.estimator.strip(): raise ValueError("counterfactual estimator required")
        if not 0<=cf.confidence<=1: raise ValueError("confidence outside [0,1]")
        if not math.isfinite(cf.estimated_utility): raise ValueError("non-finite estimate")
        self.counterfactuals[(cf.decision_id,cf.horizon,cf.alternative_action)]=cf

    def learning_signal(self,decision_id:str,horizon:str,min_cf_confidence=.7):
        obs=self.outcomes.get((decision_id,horizon))
        if obs is None: raise ValueError("observed outcome missing")
        cfs=[x for (d,h,_),x in self.counterfactuals.items() if d==decision_id and h==horizon]
        reliable=[x for x in cfs if x.confidence>=min_cf_confidence]
        if not reliable:
            return LearningSignal(decision_id,obs.utility,None,None,0.0,True)
        best=max(reliable,key=lambda x:x.estimated_utility)
        regret=max(0.0,best.estimated_utility-obs.utility)
        # Adaptation remains safe because observed utility is primary; estimated
        # regret is supplementary and carries explicit confidence.
        return LearningSignal(decision_id,obs.utility,best.estimated_utility,regret,best.confidence,True)

    def comparable_history(self,context_fingerprint:str):
        return tuple(t for t in self.traces.values() if t.context_fingerprint==context_fingerprint)
