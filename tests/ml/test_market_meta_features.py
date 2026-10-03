from strattester.ml.features import build_feature_rows
from strattester.ml.market_features import enrich_research_features,attach_external_series
from strattester.ml.meta import StrategyObservation,attach_strategy_features,StrategyMetaModel
from strattester.ml.stability import feature_stability

def bars(n=80):
    out=[]; p=100.0
    for i in range(n):
        p+=1.0 if (i//8)%2==0 else -0.7
        out.append({'t':i*60000,'open':p-.2,'high':p+.8,'low':p-.8,'close':p,'volume':100+i,'turnover':10000+i})
    return out

def test_research_enrichment_is_causal_and_contains_structure_features():
    b=bars()
    rows=enrich_research_features(build_feature_rows(b),b)
    last=rows[-1]
    for key in ('distance_poc','distance_vah','distance_val','value_area_width_pct',
                'distance_period_high','distance_period_low','vol_atr_pct','vol_percentile'):
        assert key in last.values
    assert last.known_at==b[-1]['t']+60000

def test_external_series_never_reads_after_feature_known_at():
    b=bars(3); rows=build_feature_rows(b)
    enriched=attach_external_series(rows,open_interest=[
        {'open_time':0,'known_at':60000,'value':100},
        {'open_time':999999,'known_at':999999,'value':999},
    ])
    assert enriched[0].values['open_interest']==100
    assert enriched[-1].values['open_interest']==100

def test_strategy_observations_become_meta_features():
    rows=build_feature_rows(bars(4))
    obs=[StrategyObservation(rows[1].timestamp,'smc_ob',1,.8,1.2,known_at=rows[1].known_at)]
    out=attach_strategy_features(rows,obs)
    assert out[1].values['strategy_smc_ob_direction']==1
    assert out[1].values['strategy_smc_ob_confidence']==.8
    assert 'strategy_smc_ob_direction' not in out[0].values

def test_meta_model_and_stability_report():
    rows=build_feature_rows(bars(30))
    labels=[1 if x.values['return_1']>0 else 0 for x in rows]
    model=StrategyMetaModel().fit(rows,labels)
    p=model.predict(rows[-1])
    assert 0<=p.probability_up<=1
    assert model.important_interactions()
    stable=feature_stability([
        {'delta':1.0,'noise':1.0},
        {'delta':.8,'noise':-1.0},
        {'delta':.6,'noise':1.0},
        {'delta':.9,'noise':-1.0},
    ])
    d=next(x for x in stable if x.name=='delta')
    n=next(x for x in stable if x.name=='noise')
    assert d.stable and not n.stable


def test_future_strategy_observation_is_rejected_from_feature_row():
    rows=build_feature_rows(bars(3))
    obs=[StrategyObservation(rows[1].timestamp,'future',1,.9,2.0,known_at=rows[1].known_at+1)]
    out=attach_strategy_features(rows,obs)
    assert 'strategy_future_direction' not in out[1].values
