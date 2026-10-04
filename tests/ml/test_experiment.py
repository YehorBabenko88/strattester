from strattester.ml.experiment import run_experiment

def bars(n=700):
    out=[]; p=100.0
    for i in range(n):
        drift=.22 if (i//35)%2==0 else -.18
        p=max(10,p+drift)
        out.append({'t':i*60000,'open':p-drift,'high':p+.4,'low':p-.4,'close':p,'volume':100+i%17,'turnover':10000+i})
    return out

def test_experiment_runs_oos_training_then_holdout_simulation():
    result,pipeline=run_experiment('BTCUSDT',bars(),horizon=5,train_size=180,test_size=50,simulation_fraction=.20)
    assert result.symbol=='BTCUSDT'
    assert result.train_samples>0
    assert 0<=result.oos_accuracy<=1
    assert 0<=result.oos_brier<=1
    assert result.stable_features
    assert result.model_trained_until==pipeline.snapshot.trained_until
    assert 'trades' in result.simulation


def test_experiment_reports_oos_baselines_and_probability_diagnostics():
    b=bars(700)
    result,_=run_experiment('BTCUSDT',b,horizon=5,train_size=180,test_size=50,simulation_fraction=.20)
    d=result.diagnostics
    assert 0.0<=d['positive_rate']<=1.0
    # A causal constant-class baseline is chosen from each train window.
    # It can score below 0.5 accuracy and above 0.25 Brier on a shifted test window.
    assert 0.0<=d['naive_accuracy']<=1.0
    assert 0.0<=d['naive_brier']<=1.0
    assert d['probability_min']<=d['probability_mean']<=d['probability_max']
    assert set(d['probability_quantiles'])=={'p01','p05','p25','p50','p75','p95','p99'}
    assert set(d['signal_counts'])=={'0.55','0.6','0.65'}
    assert d['windows']


def test_experiment_reports_acceptance_regimes_holdout_and_timings():
    result,_=run_experiment('BTCUSDT',bars(700),horizon=5,train_size=180,test_size=50,simulation_fraction=.20)
    d=result.diagnostics
    assert isinstance(d['model_accepted'],bool)
    assert isinstance(d['rejection_reasons'],list)
    assert set(d['timing_seconds'])=={'fit','simulation','total'}
    assert d['timing_seconds']['fit']>=0
    assert d['holdout']['predictions']>0
    assert set(d['holdout']['signal_counts'])=={'0.55','0.6','0.65'}
    assert isinstance(d['regimes'],dict)
    if not d['model_accepted']:
        assert d['rejection_reasons']
        assert d['hypothetical_simulation_if_rejected'] is not None


def test_experiment_compares_candidate_models():
    result,_=run_experiment('BTCUSDT',bars(700),horizon=5,train_size=180,test_size=50,simulation_fraction=.20)
    d=result.diagnostics
    assert d['model_name'] in d['candidate_models']
    assert 'logistic_l2_1e-4' in d['candidate_models']
    assert 'balanced_l2_1e-4' in d['candidate_models']
    assert len(d['candidate_models'])==6
    selected=d['candidate_models'][d['model_name']]
    assert selected['brier']==min(x['brier'] for x in d['candidate_models'].values())


def test_experiment_reports_causal_baselines_calibration_and_input_audit():
    result,_=run_experiment('BTCUSDT',bars(700),horizon=5,train_size=180,test_size=50,simulation_fraction=.20)
    d=result.diagnostics
    assert d['calibration']
    assert d['input_sources']['bars']==700
    assert d['input_sources']['bar_ms']==60000
    assert d['input_sources']['open_interest']==0
    assert d['input_sources']['forecast_provider'] is False
    assert d['input_sources']['microstructure']==0
    assert d['feature_family_usage']['microstructure']['available_features']>=1
    assert d['feature_family_usage']
    for w in d['windows']:
        assert 0.0<=w['train_positive_rate']<=1.0
        assert 0.0<=w['naive_brier']<=1.0
