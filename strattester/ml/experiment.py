from __future__ import annotations
from dataclasses import dataclass,asdict
from .pipeline import ResearchMLPipeline
from .simulation import MLSimulationPolicy,simulate_frozen_pipeline
from strattester.research.statistics import evaluate_trades

@dataclass(frozen=True)
class ExperimentResult:
    symbol:str
    horizon:int
    train_samples:int
    oos_accuracy:float
    oos_brier:float
    stable_features:tuple[str,...]
    simulation:dict
    model_trained_until:int

    def to_dict(self):
        d=asdict(self); d['stable_features']=list(self.stable_features); return d

def run_experiment(symbol,bars,*,horizon=15,train_size=500,test_size=100,
                   simulation_fraction=.20,policy=None,public_trade_aggregates=(),**feature_kwargs):
    rows=sorted((dict(x) for x in bars),key=lambda x:int(x['t']))
    if len(rows)<max(train_size+test_size+horizon+10,100):
        raise ValueError('not enough bars for experiment')
    cut=max(1,min(len(rows)-1,int(len(rows)*(1.0-float(simulation_fraction)))))
    training=rows[:cut]
    pipeline=ResearchMLPipeline(horizon=horizon)
    report=pipeline.fit_walk_forward(
        training,public_trade_aggregates,train_size=train_size,test_size=test_size,purge=horizon,**feature_kwargs)
    start=pipeline.snapshot.trained_until+horizon*60_000
    simulation=[x for x in rows[cut:] if int(x['t'])>=start]
    context=[x for x in rows if int(x['t'])<start]
    trades=()
    if simulation:
        trades=simulate_frozen_pipeline(
            pipeline,context,simulation,policy=policy or MLSimulationPolicy(),
            public_trade_aggregates=public_trade_aggregates,simulation_start_ms=start,purge=horizon,**feature_kwargs)
    metrics=asdict(evaluate_trades(trades))
    return ExperimentResult(
        symbol=symbol,horizon=horizon,train_samples=report.samples,oos_accuracy=report.accuracy,
        oos_brier=report.brier,stable_features=report.stable_features,simulation=metrics,
        model_trained_until=pipeline.snapshot.trained_until),pipeline
