import pytest
from strattester.ml.pipeline import ResearchMLPipeline
from strattester.ml.simulation import MLSimulationPolicy,simulate_frozen_pipeline

def bars(n=360):
    out=[]; p=100.0
    for i in range(n):
        phase=(i//24)%4
        drift=(.35 if phase==0 else -.30 if phase==1 else .12 if phase==2 else -.08)
        p=max(5.0,p+drift)
        out.append({'t':i*60000,'open':p-drift,'high':p+.5,'low':p-.5,'close':p,
                    'volume':100+(i%20)*3,'turnover':10000+i*5})
    return out

def test_walk_forward_training_selects_features_and_freezes_snapshot():
    b=bars(280)
    p=ResearchMLPipeline(horizon=5)
    report=p.fit_walk_forward(b,train_size=100,test_size=30,purge=5)
    assert report.samples>0
    assert report.windows
    assert report.stable_features
    assert p.snapshot is report.snapshot
    assert p.snapshot.feature_names
    assert p.snapshot.trained_until>b[-6]['t']

def test_simulation_guard_rejects_overlap_with_training_labels_and_purge():
    b=bars(280)
    p=ResearchMLPipeline(horizon=5)
    p.fit_walk_forward(b,train_size=100,test_size=30,purge=5)
    with pytest.raises(ValueError):
        p.assert_simulation_safe(simulation_start_ms=p.snapshot.trained_until+4*60000,bar_ms=60000,purge=5)
    assert p.assert_simulation_safe(simulation_start_ms=p.snapshot.trained_until+5*60000,bar_ms=60000,purge=5)

def test_simulation_uses_frozen_model_without_retraining():
    all_bars=bars(420)
    training=all_bars[:300]
    p=ResearchMLPipeline(horizon=5)
    p.fit_walk_forward(training,train_size=120,test_size=30,purge=5)
    before_weights=tuple(p.snapshot.model.weights)
    start=p.snapshot.trained_until+5*60000
    simulation=[x for x in all_bars if x['t']>=start][:80]
    context=[x for x in all_bars if x['t']<start]
    trades=simulate_frozen_pipeline(
        p,context,simulation,
        policy=MLSimulationPolicy(probability_threshold=.50,min_confidence=0.0,bar_ms=60000),
        simulation_start_ms=start,purge=5)
    assert isinstance(trades,tuple)
    assert tuple(p.snapshot.model.weights)==before_weights
    assert p.snapshot is not None
    for t in trades:
        assert t.entry_time>=start
        assert t.metadata['model_trained_until']==p.snapshot.trained_until

def test_plain_fit_is_not_accepted_for_simulation():
    b=bars(120)
    p=ResearchMLPipeline(horizon=5).fit(b)
    with pytest.raises(RuntimeError):
        simulate_frozen_pipeline(p,b[:100],b[100:])


def test_simulation_precomputes_feature_rows_once(monkeypatch):
    all_bars=bars(420)
    training=all_bars[:300]
    p=ResearchMLPipeline(horizon=5)
    p.fit_walk_forward(training,train_size=120,test_size=30,purge=5)
    start=p.snapshot.trained_until+5*60000
    simulation=[x for x in all_bars if x['t']>=start][:80]
    context=[x for x in all_bars if x['t']<start]
    calls=0
    original=p.feature_rows

    def counted(*args,**kwargs):
        nonlocal calls
        calls+=1
        return original(*args,**kwargs)

    monkeypatch.setattr(p,'feature_rows',counted)
    simulate_frozen_pipeline(
        p,context,simulation,
        policy=MLSimulationPolicy(probability_threshold=.50,min_confidence=0.0,bar_ms=60000),
        simulation_start_ms=start,purge=5)
    assert calls==1


def test_simulation_can_report_frozen_holdout_diagnostics():
    all_bars=bars(420)
    p=ResearchMLPipeline(horizon=5)
    p.fit_walk_forward(all_bars[:300],train_size=120,test_size=30,purge=5)
    start=p.snapshot.trained_until+5*60000
    simulation=[x for x in all_bars if x['t']>=start][:80]
    context=[x for x in all_bars if x['t']<start]
    diagnostics={}
    simulate_frozen_pipeline(
        p,context,simulation,
        policy=MLSimulationPolicy(probability_threshold=.60,min_confidence=.20,bar_ms=60000),
        simulation_start_ms=start,purge=5,diagnostics=diagnostics)
    assert diagnostics['predictions']>0
    assert 0.0<=diagnostics['probability_min']<=diagnostics['probability_max']<=1.0
    assert set(diagnostics['probability_quantiles'])=={'p01','p05','p25','p50','p75','p95','p99'}
    assert set(diagnostics['signal_counts'])=={'0.55','0.6','0.65'}
    assert diagnostics['policy_eligible']>=0
