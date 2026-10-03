from __future__ import annotations
from dataclasses import dataclass
from math import exp

@dataclass(frozen=True)
class ModelPrediction:
    probability_up:float
    score:float

class LogisticBaseline:
    def __init__(self, *, learning_rate=.05, epochs=300, l2=1e-4):
        self.learning_rate=float(learning_rate); self.epochs=int(epochs); self.l2=float(l2)
        self.feature_names=(); self.means={}; self.scales={}; self.weights=[]; self.bias=0.0

    @staticmethod
    def _sigmoid(x):
        if x>=0:
            z=exp(-x); return 1/(1+z)
        z=exp(x); return z/(1+z)

    def fit(self, rows, labels):
        rows=list(rows); labels=[int(x) for x in labels]
        if not rows or len(rows)!=len(labels):raise ValueError('rows and labels must be non-empty and aligned')
        self.feature_names=tuple(sorted(rows[0]))
        self.means={k:sum(float(r.get(k,0.0)) for r in rows)/len(rows) for k in self.feature_names}
        self.scales={}
        for k in self.feature_names:
            m=self.means[k]; v=sum((float(r.get(k,0.0))-m)**2 for r in rows)/len(rows)
            self.scales[k]=v**0.5 or 1.0
        xs=[[ (float(r.get(k,0.0))-self.means[k])/self.scales[k] for k in self.feature_names] for r in rows]
        self.weights=[0.0]*len(self.feature_names); self.bias=0.0
        for _ in range(self.epochs):
            gw=[0.0]*len(self.weights); gb=0.0
            for x,y in zip(xs,labels):
                p=self._sigmoid(self.bias+sum(w*v for w,v in zip(self.weights,x)))
                e=p-y; gb+=e
                for j,v in enumerate(x):gw[j]+=e*v
            n=len(xs)
            for j in range(len(self.weights)):
                self.weights[j]-=self.learning_rate*(gw[j]/n+self.l2*self.weights[j])
            self.bias-=self.learning_rate*gb/n
        return self

    def predict_one(self,row):
        if not self.feature_names:raise RuntimeError('model is not fitted')
        x=[(float(row.get(k,0.0))-self.means[k])/self.scales[k] for k in self.feature_names]
        score=self.bias+sum(w*v for w,v in zip(self.weights,x))
        return ModelPrediction(self._sigmoid(score),score)

    def coefficients(self):
        return tuple((k,w) for k,w in zip(self.feature_names,self.weights))

    def feature_importance(self):
        return tuple(sorted(((k,abs(w)) for k,w in self.coefficients()),key=lambda x:x[1],reverse=True))
