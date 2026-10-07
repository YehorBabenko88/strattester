"""Structural memory for invariant scientific market states.

Stores equivalence-class signatures rather than absolute market levels. The Brain
can therefore recognize a previously studied structure after admissible
transformations, while novel or unstable structures remain fail-closed.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter,defaultdict
from hashlib import sha256
import json
from typing import Hashable,Mapping,Sequence,Callable

def _stable(value):
    if isinstance(value,float): return round(value,8)
    if isinstance(value,dict): return {str(k):_stable(v) for k,v in sorted(value.items(),key=lambda x:str(x[0]))}
    if isinstance(value,(list,tuple)): return [_stable(v) for v in value]
    return value

def structural_signature(features:Mapping[str,object],invariant_keys:Sequence[str]):
    """Deterministic identity from explicitly declared invariant features only."""
    payload={k:_stable(features[k]) for k in sorted(set(invariant_keys)) if k in features}
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True)
    return sha256(raw.encode()).hexdigest()

@dataclass(frozen=True)
class StructuralObservation:
    signature:str
    regime:str
    utility:float
    confidence:float
    transformed_from:str|None=None

@dataclass(frozen=True)
class StructuralExperience:
    signature:str
    samples:int
    mean_utility:float
    positive_rate:float
    confidence:float
    regimes:tuple[str,...]
    familiar:bool

@dataclass(frozen=True)
class StructuralTransition:
    source:str
    target:str
    count:int
    probability:float

class StructuralMemory:
    def __init__(self,*,min_samples=6,min_confidence=.65):
        self.min_samples=int(min_samples);self.min_confidence=float(min_confidence)
        self._obs=defaultdict(list);self._transitions=Counter();self._last:str|None=None

    def observe(self,o:StructuralObservation):
        if not 0<=o.confidence<=1:raise ValueError("confidence outside [0,1]")
        self._obs[o.signature].append(o)
        if self._last is not None:self._transitions[(self._last,o.signature)]+=1
        self._last=o.signature

    def experience(self,signature:str):
        xs=self._obs.get(signature,[])
        if not xs:return StructuralExperience(signature,0,0,0,0,(),False)
        weights=[max(0,x.confidence) for x in xs];den=sum(weights)
        mean=sum(x.utility*w for x,w in zip(xs,weights))/den if den else 0
        pos=sum(w for x,w in zip(xs,weights) if x.utility>0)/den if den else 0
        conf=sum(weights)/len(weights)
        familiar=len(xs)>=self.min_samples and conf>=self.min_confidence
        return StructuralExperience(signature,len(xs),mean,pos,conf,
                                    tuple(sorted({x.regime for x in xs})),familiar)

    def transition(self,source:str,target:str):
        n=self._transitions[(source,target)]
        total=sum(v for (s,_),v in self._transitions.items() if s==source)
        return StructuralTransition(source,target,n,n/total if total else 0)

    def novelty(self,signature:str):
        e=self.experience(signature)
        return 1.0 if not e.samples else 1/(1+e.samples)

    def execution_permission(self,signature:str,*,min_mean_utility:float|None=None):
        e=self.experience(signature)
        if not e.familiar:return False,("structural_class_unfamiliar",)
        reasons=[]
        if min_mean_utility is not None and e.mean_utility<min_mean_utility:
            reasons.append("structural_class_poor_history")
        return not reasons,tuple(reasons)

    def equivalent(self,a:Mapping[str,object],b:Mapping[str,object],keys:Sequence[str]):
        return structural_signature(a,keys)==structural_signature(b,keys)
