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
