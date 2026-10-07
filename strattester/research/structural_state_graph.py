"""Graph of invariant structural market states.

Nodes are structural equivalence classes; directed edges are observed transitions.
Prediction is empirical and confidence-gated. Novel transitions remain visible but
cannot silently become execution authority.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter,defaultdict
from math import log2

@dataclass(frozen=True)
class StateNode:
    signature:str
    visits:int
    mean_utility:float
    regimes:tuple[str,...]

@dataclass(frozen=True)
class TransitionForecast:
    source:str
    ranked:tuple[tuple[str,float,int],...]
    entropy:float
    confidence:float
    familiar:bool

class StructuralStateGraph:
    def __init__(self,*,min_transition_samples=5,min_confidence=.65):
        self.min_transition_samples=int(min_transition_samples)
        self.min_confidence=float(min_confidence)
        self._visits=Counter();self._utility=defaultdict(list);self._regimes=defaultdict(set)
        self._edges=Counter();self._last=None

    def observe(self,signature:str,*,regime:str,utility:float=0.0):
        self._visits[signature]+=1;self._utility[signature].append(float(utility));self._regimes[signature].add(regime)
        if self._last is not None:self._edges[(self._last,signature)]+=1
        self._last=signature

    def node(self,signature:str):
        xs=self._utility.get(signature,[])
        return StateNode(signature,self._visits[signature],sum(xs)/len(xs) if xs else 0.0,
                         tuple(sorted(self._regimes.get(signature,set()))))

    def forecast(self,source:str):
        outs=[(t,n) for (s,t),n in self._edges.items() if s==source]
        total=sum(n for _,n in outs)
        if not total:return TransitionForecast(source,(),0.0,0.0,False)
        ranked=tuple(sorted(((t,n/total,n) for t,n in outs),key=lambda x:(-x[1],x[0])))
        entropy=-sum(p*log2(p) for _,p,_ in ranked if p>0)
        # Confidence rises with samples and falls as transition distribution becomes diffuse.
        max_entropy=log2(len(ranked)) if len(ranked)>1 else 0.0
        concentration=1.0 if max_entropy==0 else max(0.0,1-entropy/max_entropy)
        sample_factor=min(1.0,total/max(1,self.min_transition_samples))
        confidence=.5*sample_factor+.5*concentration
        familiar=total>=self.min_transition_samples and confidence>=self.min_confidence
        return TransitionForecast(source,ranked,entropy,confidence,familiar)

    def predicted_targets(self,source:str,*,min_probability=.1):
        f=self.forecast(source)
        if not f.familiar:return ()
        return tuple(t for t,p,_ in f.ranked if p>=min_probability)

    def transition_surprise(self,source:str,target:str):
        f=self.forecast(source)
        probs={t:p for t,p,_ in f.ranked}
        p=probs.get(target,0.0)
        return 1.0 if p<=0 else min(1.0,-log2(p)/16)

    def execution_permission(self,source:str):
        f=self.forecast(source)
        if not f.familiar:return False,("transition_graph_unfamiliar",)
        return True,()
