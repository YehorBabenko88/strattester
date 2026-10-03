from __future__ import annotations
from dataclasses import dataclass
from math import exp, isfinite

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

    @staticmethod
    def _finite_value(value, *, feature, row_index=None):
        try:
            value=float(value)
        except (TypeError, ValueError) as exc:
            where='' if row_index is None else f' in row {row_index}'
            raise ValueError(f'feature {feature!r}{where} must be numeric') from exc
        if not isfinite(value):
            where='' if row_index is None else f' in row {row_index}'
            raise ValueError(f'feature {feature!r}{where} must be finite')
        return value

    def fit(self, rows, labels):
        rows=list(rows); labels=[int(x) for x in labels]
        if not rows or len(rows)!=len(labels):raise ValueError('rows and labels must be non-empty and aligned')
        self.feature_names=tuple(sorted({k for row in rows for k in row}))
        if not self.feature_names:raise ValueError('rows must contain at least one feature')
        clean=[]
        for i,row in enumerate(rows):
            clean.append({k:self._finite_value(row.get(k,0.0),feature=k,row_index=i) for k in self.feature_names})
        self.means={k:sum(r[k] for r in clean)/len(clean) for k in self.feature_names}
        self.scales={}
        for k in self.feature_names:
            mean=self.means[k]; variance=sum((r[k]-mean)**2 for r in clean)/len(clean)
            self.scales[k]=variance**0.5 or 1.0
        xs=[[(r[k]-self.means[k])/self.scales[k] for k in self.feature_names] for r in clean]
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
        values={k:self._finite_value(row.get(k,0.0),feature=k) for k in self.feature_names}
        x=[(values[k]-self.means[k])/self.scales[k] for k in self.feature_names]
        score=self.bias+sum(w*v for w,v in zip(self.weights,x))
        return ModelPrediction(self._sigmoid(score),score)

    def coefficients(self):
        return tuple((k,w) for k,w in zip(self.feature_names,self.weights))

    def feature_importance(self):
        return tuple(sorted(((k,abs(w)) for k,w in self.coefficients()),key=lambda x:x[1],reverse=True))


class BalancedLogisticBaseline(LogisticBaseline):
    """Logistic baseline with inverse-frequency class weighting."""
    def fit(self,rows,labels):
        rows=list(rows); labels=[int(x) for x in labels]
        if not rows or len(rows)!=len(labels):raise ValueError('rows and labels must be non-empty and aligned')
        self.feature_names=tuple(sorted({k for row in rows for k in row}))
        if not self.feature_names:raise ValueError('rows must contain at least one feature')
        clean=[]
        for i,row in enumerate(rows):
            clean.append({k:self._finite_value(row.get(k,0.0),feature=k,row_index=i) for k in self.feature_names})
        self.means={k:sum(r[k] for r in clean)/len(clean) for k in self.feature_names}
        self.scales={}
        for k in self.feature_names:
            mean=self.means[k]; variance=sum((r[k]-mean)**2 for r in clean)/len(clean)
            self.scales[k]=variance**0.5 or 1.0
        xs=[[(r[k]-self.means[k])/self.scales[k] for k in self.feature_names] for r in clean]
        pos=sum(labels); neg=len(labels)-pos
        pos_w=len(labels)/(2*pos) if pos else 1.0
        neg_w=len(labels)/(2*neg) if neg else 1.0
        sample_weights=[pos_w if y else neg_w for y in labels]
        self.weights=[0.0]*len(self.feature_names); self.bias=0.0
        for _ in range(self.epochs):
            gw=[0.0]*len(self.weights); gb=0.0; total_w=sum(sample_weights)
            for x,y,sw in zip(xs,labels,sample_weights):
                p=self._sigmoid(self.bias+sum(w*v for w,v in zip(self.weights,x)))
                e=(p-y)*sw; gb+=e
                for j,v in enumerate(x):gw[j]+=e*v
            for j in range(len(self.weights)):
                self.weights[j]-=self.learning_rate*(gw[j]/total_w+self.l2*self.weights[j])
            self.bias-=self.learning_rate*gb/total_w
        return self
