"""Conservative credit assignment for scientific channels."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from math import sqrt
from typing import Sequence
from .decision_memory import LearningSignal

@dataclass(frozen=True)
class CreditReport:
    channel_id:str
    samples:int
    mean_score:float
    standard_error:float
    confidence_margin:float
    verdict:str
    modulation:float

class CreditAssigner:
    def __init__(self,*,min_samples=8,z=1.96,max_modulation=.15):
        self.min_samples=int(min_samples);self.z=float(z)
        self.max_modulation=float(max_modulation)
        self._scores=defaultdict(list)

    def add(self,channel_id:str,signal:LearningSignal,attribution:float=1.0):
        # Counterfactual regret is supplementary and confidence-discounted.
        score=float(signal.realized_utility)*float(attribution)
        if signal.regret is not None:
            score-=float(signal.regret)*float(signal.counterfactual_confidence)*.25*abs(float(attribution))
        self._scores[channel_id].append(score)

    def assess(self,channel_id:str):
        xs=self._scores.get(channel_id,[]);n=len(xs)
        if not n:return CreditReport(channel_id,0,0,float("inf"),float("inf"),"INSUFFICIENT",0)
        mean=sum(xs)/n
        if n<2:se=float("inf")
        else:
            var=sum((x-mean)**2 for x in xs)/(n-1);se=sqrt(var/n)
        margin=self.z*se
        if n<self.min_samples or not (margin<float("inf")):
            return CreditReport(channel_id,n,mean,se,margin,"INSUFFICIENT",0)
        if mean-margin>0: verdict="BENEFICIAL"
        elif mean+margin<0: verdict="HARMFUL"
        else: verdict="UNCERTAIN"
        modulation=0.0
        if verdict=="BENEFICIAL":modulation=min(self.max_modulation,max(0,mean-margin))
        elif verdict=="HARMFUL":modulation=max(-self.max_modulation,min(0,mean+margin))
        return CreditReport(channel_id,n,mean,se,margin,verdict,modulation)
