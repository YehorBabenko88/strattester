from __future__ import annotations
from dataclasses import dataclass,asdict
from .features import build_feature_rows
from .labels import build_labels
from .model import LogisticBaseline
from .validation import walk_forward_splits
from .forecasting import attach_forecast_features

@dataclass(frozen=True)
class MLSignal:
    timestamp:int
    known_at:int
    regime:str
    probability_up:float
    expected_return:float
    confidence:float
    horizon_bars:int
    top_features:tuple[tuple[str,float],...]

    def to_dict(self):
        d=asdict(self)
        d['top_features']=[{'name':k,'importance':v} for k,v in self.top_features]
        return d

@dataclass(frozen=True)
class WalkForwardMetrics:
    samples:int
    accuracy:float
    brier:float
    mean_return:float

class ResearchMLPipeline:
    def __init__(self, *, horizon=15, model_factory=LogisticBaseline, forecast_provider=None):
        self.horizon=int(horizon)
        self.model_factory=model_factory
        self.forecast_provider=forecast_provider
        self.model=None
        self.mean_up_return=0.0
        self.mean_down_return=0.0

    def dataset(self,bars,public_trade_aggregates=()):
        features=build_feature_rows(bars,public_trade_aggregates)
        features=attach_forecast_features(features,bars,self.forecast_provider,horizon=self.horizon)
        labels=build_labels(bars,horizons=(self.horizon,))
        label_by_t={x.timestamp:x for x in labels}
        rows=[]
        for f in features:
            label=label_by_t.get(f.timestamp)
            if label is not None:
                rows.append((f,label))
        return tuple(rows)

    def fit(self,bars,public_trade_aggregates=()):
        ds=self.dataset(bars,public_trade_aggregates)
        if not ds:raise ValueError('not enough history for requested horizon')
        self.model=self.model_factory().fit([f.values for f,_ in ds],[y.up for _,y in ds])
        ups=[y.future_return for _,y in ds if y.up]
        downs=[y.future_return for _,y in ds if not y.up]
        self.mean_up_return=sum(ups)/len(ups) if ups else 0.0
        self.mean_down_return=sum(downs)/len(downs) if downs else 0.0
        return self

    def signal(self,bars,public_trade_aggregates=()):
        if self.model is None:raise RuntimeError('pipeline is not fitted')
        rows=build_feature_rows(bars,public_trade_aggregates)
        rows=attach_forecast_features(rows,bars,self.forecast_provider,horizon=self.horizon)
        if not rows:raise ValueError('no feature rows')
        row=rows[-1]; p=self.model.predict_one(row.values).probability_up
        expected=p*self.mean_up_return+(1-p)*self.mean_down_return
        return MLSignal(row.timestamp,row.known_at,row.regime,p,expected,abs(p-.5)*2,self.horizon,tuple(self.model.feature_importance()[:8]))

    def walk_forward(self,bars,public_trade_aggregates=(), *, train_size=500,test_size=100,purge=None):
        ds=self.dataset(bars,public_trade_aggregates)
        purge=max(self.horizon,int(purge or 0))
        splits=walk_forward_splits(len(ds),train_size=train_size,test_size=test_size,purge=purge)
        probs=[]; actual=[]; returns=[]
        for split in splits:
            model=self.model_factory().fit([ds[i][0].values for i in split.train],[ds[i][1].up for i in split.train])
            for i in split.test:
                probs.append(model.predict_one(ds[i][0].values).probability_up)
                actual.append(ds[i][1].up); returns.append(ds[i][1].future_return)
        if not probs:return WalkForwardMetrics(0,0.0,0.0,0.0)
        acc=sum((p>=.5)==bool(y) for p,y in zip(probs,actual))/len(probs)
        brier=sum((p-y)**2 for p,y in zip(probs,actual))/len(probs)
        return WalkForwardMetrics(len(probs),acc,brier,sum(returns)/len(returns))
