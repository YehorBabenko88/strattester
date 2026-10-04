from __future__ import annotations
from dataclasses import dataclass,asdict
from .features import build_feature_rows
from .labels import build_labels
from .model import LogisticBaseline
from .validation import walk_forward_splits
from .forecasting import attach_forecast_features
from .market_features import enrich_research_features,attach_external_series,attach_live_microstructure
from .meta import attach_strategy_features
from .training import train_walk_forward,assert_snapshot_safe_for_simulation

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
        self.snapshot=None
        self.mean_up_return=0.0
        self.mean_down_return=0.0

    def feature_rows(self,bars,public_trade_aggregates=(),*,open_interest=(),long_short_ratio=(),funding=(),strategy_observations=(),
                     bar_ms=60_000,open_interest_bar_ms=300_000,long_short_bar_ms=300_000,microstructure=(),micro_max_age_ms=15_000):
        features=build_feature_rows(bars,public_trade_aggregates,bar_ms=bar_ms)
        features=enrich_research_features(features,bars,bar_ms=bar_ms)
        features=attach_external_series(
            features,open_interest=open_interest,long_short_ratio=long_short_ratio,funding=funding,
            open_interest_bar_ms=open_interest_bar_ms,long_short_bar_ms=long_short_bar_ms)
        features=attach_strategy_features(features,strategy_observations)
        features=attach_live_microstructure(features,microstructure,max_age_ms=micro_max_age_ms)
        return attach_forecast_features(features,bars,self.forecast_provider,horizon=self.horizon)

    def dataset(self,bars,public_trade_aggregates=(),*,open_interest=(),long_short_ratio=(),funding=(),strategy_observations=(),
                bar_ms=60_000,open_interest_bar_ms=300_000,long_short_bar_ms=300_000,microstructure=(),micro_max_age_ms=15_000):
        features=self.feature_rows(
            bars,public_trade_aggregates,open_interest=open_interest,long_short_ratio=long_short_ratio,
            funding=funding,strategy_observations=strategy_observations,bar_ms=bar_ms,
            open_interest_bar_ms=open_interest_bar_ms,long_short_bar_ms=long_short_bar_ms)
        labels=build_labels(bars,horizons=(self.horizon,))
        label_by_t={x.timestamp:x for x in labels}
        rows=[]
        for f in features:
            label=label_by_t.get(f.timestamp)
            if label is not None:
                rows.append((f,label))
        return tuple(rows)

    def fit(self,bars,public_trade_aggregates=(),**kwargs):
        ds=self.dataset(bars,public_trade_aggregates,**kwargs)
        if not ds:raise ValueError('not enough history for requested horizon')
        self.model=self.model_factory().fit([f.values for f,_ in ds],[y.up for _,y in ds])
        ups=[y.future_return for _,y in ds if y.up]
        downs=[y.future_return for _,y in ds if not y.up]
        self.mean_up_return=sum(ups)/len(ups) if ups else 0.0
        self.mean_down_return=sum(downs)/len(downs) if downs else 0.0
        self.snapshot=None
        return self

    def fit_walk_forward(self,bars,public_trade_aggregates=(),*,train_size=500,test_size=100,purge=None,**kwargs):
        ds=self.dataset(bars,public_trade_aggregates,**kwargs)
        purge=max(self.horizon,int(purge or 0))
        report=train_walk_forward(ds,model_factory=self.model_factory,train_size=train_size,test_size=test_size,purge=purge)
        self.snapshot=report.snapshot
        self.model=report.snapshot.model
        self.mean_up_return=report.snapshot.mean_up_return
        self.mean_down_return=report.snapshot.mean_down_return
        return report

    def signal_from_feature_row(self,row):
        if self.model is None:raise RuntimeError('pipeline is not fitted')
        predictor=self.snapshot if self.snapshot is not None else self.model
        p=predictor.predict_one(row.values).probability_up
        expected=p*self.mean_up_return+(1-p)*self.mean_down_return
        return MLSignal(row.timestamp,row.known_at,row.regime,p,expected,abs(p-.5)*2,self.horizon,tuple(self.model.feature_importance()[:8]))

    def signal(self,bars,public_trade_aggregates=(),**kwargs):
        if self.model is None:raise RuntimeError('pipeline is not fitted')
        rows=self.feature_rows(
            bars,public_trade_aggregates,open_interest=kwargs.get('open_interest',()),
            long_short_ratio=kwargs.get('long_short_ratio',()),funding=kwargs.get('funding',()),
            strategy_observations=kwargs.get('strategy_observations',()),bar_ms=kwargs.get('bar_ms',60_000),
            open_interest_bar_ms=kwargs.get('open_interest_bar_ms',300_000),
            long_short_bar_ms=kwargs.get('long_short_bar_ms',300_000),microstructure=kwargs.get('microstructure',()),
            micro_max_age_ms=kwargs.get('micro_max_age_ms',15_000))
        if not rows:raise ValueError('no feature rows')
        return self.signal_from_feature_row(rows[-1])

    def assert_simulation_safe(self,*,simulation_start_ms,bar_ms=60_000,purge=None):
        if self.snapshot is None:
            raise RuntimeError('walk-forward frozen snapshot is required for simulation safety checks')
        return assert_snapshot_safe_for_simulation(self.snapshot,simulation_start_ms=int(simulation_start_ms),bar_ms=int(bar_ms),purge_bars=max(self.horizon,int(purge or 0)))

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
