"""Structural mathematics controls inspired by musical mathematics.

These are domain-neutral abstractions: transformation invariance, balanced
coverage, temporal tiling, sequence complexity and parsimonious approximation.
They do not treat musical structures as trading signals.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from math import gcd,log2
from typing import Hashable,Iterable,Mapping,Sequence,Callable

@dataclass(frozen=True)
class StructuralReport:
    invariant_score:float
    balance_score:float
    coverage_score:float
    complexity_score:float
    healthy:bool
    reasons:tuple[str,...]

def transformation_invariance(signature:Callable[[object],Hashable],states:Sequence[object],
                              transforms:Sequence[Callable[[object],object]]):
    if not states or not transforms:return 0.0
    total=ok=0
    for s in states:
        base=signature(s)
        for t in transforms:
            total+=1;ok+=signature(t(s))==base
    return ok/total

def balanced_pair_coverage(blocks:Sequence[Sequence[Hashable]]):
    """1.0 when all observed unordered pairs occur equally often."""
    counts=Counter()
    universe=set()
    for block in blocks:
        b=list(dict.fromkeys(block));universe.update(b)
        for i in range(len(b)):
            for j in range(i+1,len(b)):
                counts[tuple(sorted((repr(b[i]),repr(b[j]))))]+=1
    if len(universe)<2:return 0.0
    vals=list(counts.values())
    possible=len(universe)*(len(universe)-1)//2
    coverage=len(vals)/possible
    if not vals:return 0.0
    balance=min(vals)/max(vals)
    return coverage*balance

def temporal_tiling_score(slots:Sequence[Sequence[Hashable]],required:Iterable[Hashable]):
    """Rewards complete non-overlapping coverage of required responsibilities."""
    required=set(required);seen=Counter(x for slot in slots for x in slot if x in required)
    if not required:return 1.0
    exact=sum(1 for x in required if seen[x]==1)/len(required)
    extras=sum(max(0,n-1) for n in seen.values())
    return max(0.0,exact-extras/max(1,len(required)))

def normalized_word_complexity(word:Sequence[Hashable]):
    """Primitive/subword diversity proxy, bounded to [0,1]."""
    n=len(word)
    if n<2:return 0.0
    # Detect exact periodic collapse.
    primitive=True
    for p in range(1,n//2+1):
        if n%p==0 and list(word)==list(word[:p])*(n//p):
            primitive=False;break
    k=min(4,n)
    distinct=len({tuple(word[i:i+k]) for i in range(n-k+1)})
    diversity=distinct/max(1,n-k+1)
    return min(1.0,(.5 if primitive else 0.0)+.5*diversity)

def rational_approximation(value:float,max_denominator=64):
    """Small continued-fraction-style rational control representation."""
    from fractions import Fraction
    f=Fraction(float(value)).limit_denominator(int(max_denominator))
    error=abs(float(value)-float(f))
    return f.numerator,f.denominator,error

class StructuralMathematicsSupervisor:
    def __init__(self,*,min_invariance=.65,min_balance=.35,min_coverage=.8,min_complexity=.25):
        self.thresholds=(min_invariance,min_balance,min_coverage,min_complexity)

    def assess(self,*,invariant_score:float,balance_score:float,coverage_score:float,
               complexity_score:float):
        vals=(invariant_score,balance_score,coverage_score,complexity_score)
        reasons=[]
        names=("transformation_fragility","unbalanced_model_interactions",
               "incomplete_temporal_coverage","sequence_collapse")
        for v,t,n in zip(vals,self.thresholds,names):
            if v<t:reasons.append(n)
        return StructuralReport(*vals,not reasons,tuple(reasons))
