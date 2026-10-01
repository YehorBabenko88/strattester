import math
from strattester.research.volatility import VolatilityObservatory,VolatilityRegime

def _bar(t,o,h,l,c,v=100,turnover=10000):
    return {'t':t,'open':o,'high':h,'low':l,'close':c,'volume':v,'turnover':turnover}

def test_observatory_computes_causal_metrics_and_regime():
    bars=[
      _bar(0,100,101,99,100),
      _bar(60,100,102,99,101),
      _bar(120,101,103,100,102),
      _bar(180,102,106,101,105,200,21000),
      _bar(240,105,110,104,109,300,32700),
    ]
    obs=VolatilityObservatory(window=3,percentile_lookback=10,version='vol-v1')
    xs=obs.snapshots(bars,bar_ms=60)
    x=xs[-1]
    assert x.known_at==300
    assert x.atr_pct>0
    assert x.realized_vol>=0
    assert x.parkinson_vol>=0
    assert x.range_pct>0
    assert x.volume_expansion>1
    assert x.turnover_expansion>1
    assert x.regime in set(VolatilityRegime)

def test_future_rows_cannot_reclassify_old_snapshot():
    base=[
      _bar(0,100,101,99,100),
      _bar(60,100,102,99,101),
      _bar(120,101,103,100,102),
      _bar(180,102,104,101,103),
    ]
    future=_bar(240,103,150,50,140,10000,1400000)
    obs=VolatilityObservatory(window=2,percentile_lookback=10)
    a=obs.snapshots(base,bar_ms=60)[-1]
    b=[x for x in obs.snapshots(base+[future],bar_ms=60) if x.event_time==a.event_time][0]
    assert a==b

def test_percentile_uses_only_prior_history():
    bars=[
      _bar(0,100,101,99,100),
      _bar(60,100,101,99,100),
      _bar(120,100,102,98,101),
      _bar(180,101,106,95,104),
    ]
    xs=VolatilityObservatory(window=2,percentile_lookback=10).snapshots(bars,bar_ms=60)
    assert xs[-1].percentile>=xs[-2].percentile
