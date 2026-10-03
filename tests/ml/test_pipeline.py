from strattester.ml.pipeline import ResearchMLPipeline

def trending_bars(n=180):
    out=[]
    price=100.0
    for i in range(n):
        drift=0.35 if (i//30)%2==0 else -0.25
        price=max(1.0,price+drift)
        out.append({'t':i*60000,'open':price-drift,'high':price+0.4,'low':price-0.4,'close':price,'volume':100+abs(drift)*20,'turnover':10000})
    return out

def test_pipeline_builds_aligned_dataset_and_signal():
    b=trending_bars()
    p=ResearchMLPipeline(horizon=5)
    ds=p.dataset(b)
    assert len(ds)==len(b)-5
    assert all(f.timestamp==y.timestamp for f,y in ds)
    p.fit(b)
    s=p.signal(b)
    assert 0<=s.probability_up<=1
    assert 0<=s.confidence<=1
    assert s.known_at==b[-1]['t']+60000
    assert s.top_features
    payload=s.to_dict()
    assert payload['horizon_bars']==5
    assert isinstance(payload['top_features'],list)

def test_walk_forward_enforces_horizon_purge():
    b=trending_bars(220)
    p=ResearchMLPipeline(horizon=5)
    m=p.walk_forward(b,train_size=80,test_size=20,purge=0)
    assert m.samples>0
    assert 0<=m.accuracy<=1
    assert m.brier>=0

class FakeForecast:
    def forecast_features(self,history,*,horizon):
        return {'return':float(horizon)/1000.0,'range':len(history)/1000.0}

def test_forecast_provider_is_attached_without_future_history():
    b=trending_bars(30)
    p=ResearchMLPipeline(horizon=5,forecast_provider=FakeForecast())
    ds=p.dataset(b)
    f,_=ds[0]
    assert 'forecast_return' in f.values
    assert f.values['forecast_range']==1/1000.0
