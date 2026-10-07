"""Layered scientific inference graph.

The graph deliberately separates observations, transformations, model evidence and
meta-inference. Downstream layers consume immutable upstream artifacts so new
methods can be added without changing historical artifacts or database columns.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from hashlib import sha256
import json,math,statistics
from typing import Any,Mapping,Sequence

@dataclass(frozen=True)
class ScientificArtifact:
    method:str
    layer:str
    inputs:tuple[str,...]
    payload:Mapping[str,Any]
    confidence:float
    warnings:tuple[str,...]=()
    artifact_id:str=""

    def __post_init__(self):
        if not self.artifact_id:
            raw=json.dumps({"method":self.method,"layer":self.layer,"inputs":self.inputs,
                            "payload":self.payload,"confidence":self.confidence,
                            "warnings":self.warnings},sort_keys=True,default=str)
            object.__setattr__(self,"artifact_id",sha256(raw.encode()).hexdigest())

class ScientificGraph:
    def __init__(self): self._items:dict[str,ScientificArtifact]={}
    def add(self,a:ScientificArtifact):
        missing=[x for x in a.inputs if x not in self._items]
        if missing: raise ValueError(f"missing upstream artifacts: {missing}")
        self._items[a.artifact_id]=a; return a
    def artifacts(self): return tuple(self._items.values())
    def by_layer(self,layer): return tuple(x for x in self._items.values() if x.layer==layer)

def _finite(xs):
    return [float(x) for x in xs if x is not None and math.isfinite(float(x))]

def observation_artifact(returns:Sequence[float]):
    xs=_finite(returns)
    if len(xs)<20: raise ValueError("at least 20 finite returns required")
    mu=statistics.fmean(xs); sd=statistics.stdev(xs)
    return ScientificArtifact("descriptive_returns","OBSERVATION",(),{
        "n":len(xs),"mean":mu,"stdev":sd,
        "min":min(xs),"max":max(xs)},1.0)

def volatility_artifact(obs:ScientificArtifact,returns:Sequence[float],window:int=20):
    xs=_finite(returns)
    if len(xs)<window+1: raise ValueError("insufficient volatility history")
    rv=[statistics.pstdev(xs[i-window:i]) for i in range(window,len(xs)+1)]
    med=statistics.median(rv); latest=rv[-1]
    ratio=latest/med if med>0 else 1.0
    regime="HIGH" if ratio>=1.5 else "LOW" if ratio<=.67 else "NORMAL"
    return ScientificArtifact("rolling_conditional_volatility","VOLATILITY",(obs.artifact_id,),{
        "window":window,"latest":latest,"median":med,"ratio":ratio,"regime":regime},.75)

def nonlinear_evidence_artifact(parent:ScientificArtifact,returns:Sequence[float]):
    """Conservative nonlinear screen, not a claim that chaos was detected."""
    xs=_finite(returns)
    if len(xs)<40: raise ValueError("insufficient nonlinear history")
    # Lag-1 dependence in returns and squared returns: inexpensive precursor evidence.
    def corr(a,b):
        ma=statistics.fmean(a);mb=statistics.fmean(b)
        num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
        den=math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
        return num/den if den else 0.0
    r1=corr(xs[:-1],xs[1:]); sq=[x*x for x in xs]; q1=corr(sq[:-1],sq[1:])
    score=min(1.0,abs(r1)+abs(q1))
    return ScientificArtifact("nonlinear_residual_screen","NONLINEAR",(parent.artifact_id,),{
        "return_lag1":r1,"squared_return_lag1":q1,"evidence_score":score,
        "chaos_claim":False},.6,("screen_only_requires_formal_nonlinearity_and_chaos_tests",))

def regime_artifact(vol:ScientificArtifact,nonlinear:ScientificArtifact):
    v=vol.payload["regime"]; n=float(nonlinear.payload["evidence_score"])
    regime=f"{v}_NONLINEAR" if n>=.25 else f"{v}_WEAK_NONLINEAR"
    confidence=min(float(vol.confidence),float(nonlinear.confidence))
    return ScientificArtifact("regime_synthesis","REGIME",(vol.artifact_id,nonlinear.artifact_id),{
        "regime":regime,"nonlinear_score":n},confidence)

def robustness_artifact(model:ScientificArtifact,parameter_results:Sequence[Mapping[str,Any]]):
    """Barnett-style neighborhood check: decisions must not rely on one point estimate."""
    rows=list(parameter_results)
    if not rows: raise ValueError("parameter neighborhood is empty")
    labels=[str(x.get("regime","UNKNOWN")) for x in rows]
    counts={x:labels.count(x) for x in sorted(set(labels))}
    dominant=max(counts,key=counts.get)
    share=counts[dominant]/len(labels)
    boundary=len(counts)>1
    return ScientificArtifact("parameter_neighborhood_robustness","ROBUSTNESS",(model.artifact_id,),{
        "samples":len(rows),"regimes":counts,"dominant_regime":dominant,
        "dominant_share":share,"boundary_crossed":boundary,
        "point_estimate_only":False},share,
        ("parameter_region_crosses_regime_boundary",) if boundary else ())

def pattern_artifact(parents:Sequence[ScientificArtifact]):
    if not parents: raise ValueError("at least one parent required")
    regimes=[str(x.payload.get("regime","")) for x in parents if x.payload.get("regime")]
    consensus=(max(set(regimes),key=regimes.count) if regimes else "UNKNOWN")
    agreement=(regimes.count(consensus)/len(regimes) if regimes else 0.0)
    return ScientificArtifact("cross_model_pattern","META",tuple(x.artifact_id for x in parents),{
        "consensus":consensus,"agreement":agreement,"evidence_count":len(parents)},agreement)
