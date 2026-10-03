from __future__ import annotations
from dataclasses import dataclass
from .model import LogisticBaseline

@dataclass(frozen=True)
class StrategyObservation:
    timestamp:int
    strategy_id:str
    direction:int=0
    confidence:float=0.0
    expected_r:float=0.0

def attach_strategy_features(rows,observations):
    by_t={}
    for x in observations:
        by_t.setdefault(int(x.timestamp),[]).append(x)
    out=[]
    for row in rows:
        values=dict(row.values)
        obs=by_t.get(int(row.timestamp),())
        for x in obs:
            prefix='strategy_'+str(x.strategy_id).lower()
            values[prefix+'_direction']=float(x.direction)
            values[prefix+'_confidence']=float(x.confidence)
            values[prefix+'_expected_r']=float(x.expected_r)
        out.append(type(row)(row.timestamp,row.known_at,values,row.regime))
    return tuple(out)

class StrategyMetaModel:
    def __init__(self,model_factory=LogisticBaseline):
        self.model_factory=model_factory; self.model=None

    def fit(self,feature_rows,labels):
        self.model=self.model_factory().fit([x.values for x in feature_rows],labels)
        return self

    def predict(self,feature_row):
        if self.model is None:raise RuntimeError('meta model is not fitted')
        return self.model.predict_one(feature_row.values)

    def important_interactions(self,limit=12):
        if self.model is None:return ()
        return tuple(self.model.feature_importance()[:int(limit)])
