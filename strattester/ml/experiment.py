from __future__ import annotations
from dataclasses import dataclass,asdict
from time import perf_counter
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
    diagnostics:dict

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
    effective_policy=policy or MLSimulationPolicy()
    fit_started=perf_counter()
    report=pipeline.fit_walk_forward(
        training,public_trade_aggregates,train_size=train_size,test_size=test_size,purge=horizon,**feature_kwargs)
    fit_seconds=perf_counter()-fit_started
    start=pipeline.snapshot.trained_until+horizon*effective_policy.bar_ms
    simulation=[x for x in rows[cut:] if int(x['t'])>=start]
    context=[x for x in rows if int(x['t'])<start]
    trades=()
    holdout_diagnostics={}
    simulation_seconds=0.0
    if simulation:
        simulation_started=perf_counter()
        trades=simulate_frozen_pipeline(
            pipeline,context,simulation,policy=effective_policy,
            public_trade_aggregates=public_trade_aggregates,simulation_start_ms=start,purge=horizon,
            diagnostics=holdout_diagnostics,**feature_kwargs)
        simulation_seconds=perf_counter()-simulation_started
    hypothetical_metrics=asdict(evaluate_trades(trades))
    metrics=hypothetical_metrics if report.accepted else asdict(evaluate_trades(()))
    return ExperimentResult(
        symbol=symbol,horizon=horizon,train_samples=report.samples,oos_accuracy=report.accuracy,
        oos_brier=report.brier,stable_features=report.stable_features,simulation=metrics,
        model_trained_until=pipeline.snapshot.trained_until,
        diagnostics={
            'positive_rate':report.positive_rate,
            'naive_accuracy':report.naive_accuracy,
            'naive_brier':report.naive_brier,
            'probability_min':report.probability_min,
            'probability_max':report.probability_max,
            'probability_mean':report.probability_mean,
            'probability_quantiles':dict(zip(('p01','p05','p25','p50','p75','p95','p99'),report.probability_quantiles)),
            'signal_counts':{str(k):v for k,v in report.signal_counts},
            'model_accepted':report.accepted,
            'rejection_reasons':list(report.rejection_reasons),
            'timing_seconds':{'fit':fit_seconds,'simulation':simulation_seconds,'total':fit_seconds+simulation_seconds},
            'holdout':holdout_diagnostics,
            'hypothetical_simulation_if_rejected':hypothetical_metrics if not report.accepted else None,
            'regimes':{name:{
                'samples':samples,'positive_rate':positive_rate,'accuracy':accuracy,'brier':brier
            } for name,samples,positive_rate,accuracy,brier in report.regime_metrics},
            'windows':[{
                'train_start':w.train_start,'train_end':w.train_end,
                'test_start':w.test_start,'test_end':w.test_end,'samples':w.samples,
                'accuracy':w.accuracy,'brier':w.brier,'positive_rate':w.positive_rate,
                'naive_accuracy':w.naive_accuracy,'naive_brier':w.naive_brier,
                'probability_min':w.probability_min,'probability_max':w.probability_max,
                'probability_mean':w.probability_mean} for w in report.windows],
        }),pipeline
