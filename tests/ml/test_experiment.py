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
    assert d['naive_accuracy']>=0.5
    assert 0.0<=d['naive_brier']<=0.25
    assert d['probability_min']<=d['probability_mean']<=d['probability_max']
    assert set(d['probability_quantiles'])=={'p01','p05','p25','p50','p75','p95','p99'}
    assert set(d['signal_counts'])=={'0.55','0.6','0.65'}
    assert d['windows']
