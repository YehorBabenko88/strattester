from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FeatureStability:
    name:str
    windows:int
    positive:int
    negative:int
    mean_importance:float
    stable:bool

def feature_stability(importances_by_window,*,min_windows=3,min_direction_share=.75):
    buckets={}
    for window in importances_by_window:
        for name,value in window.items():
            buckets.setdefault(name,[]).append(float(value))
    out=[]
    for name,vals in buckets.items():
        pos=sum(x>0 for x in vals); neg=sum(x<0 for x in vals); n=len(vals)
        share=max(pos,neg)/n if n else 0.0
        out.append(FeatureStability(name,n,pos,neg,sum(abs(x) for x in vals)/n if n else 0.0,n>=min_windows and share>=min_direction_share))
    return tuple(sorted(out,key=lambda x:(x.stable,x.mean_importance),reverse=True))
