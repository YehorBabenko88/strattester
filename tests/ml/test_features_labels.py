from strattester.ml.features import build_feature_rows
from strattester.ml.labels import build_labels

def bars(n=12):
    out=[]
    for i in range(n):
        c=100+i
        out.append({'t':i*60000,'open':c-0.5,'high':c+1,'low':c-1,'close':c,'volume':10+i,'turnover':1000+i})
    return out

def test_features_are_causal_and_known_after_bar_close():
    xs=build_feature_rows(bars(4),bar_ms=60000)
    assert [x.timestamp for x in xs]==[0,60000,120000,180000]
    assert [x.known_at for x in xs]==[60000,120000,180000,240000]
    first=xs[0].values
    assert first['return_1']==0.0
    assert first['return_3']==0.0

def test_orderflow_features_only_use_matching_completed_minute():
    flow=[
        {'open_time':0,'buy_volume':7,'sell_volume':3},
        {'open_time':60000,'buy_volume':2,'sell_volume':8},
    ]
    xs=build_feature_rows(bars(2),flow)
    assert xs[0].values['delta']==4
    assert xs[0].values['cvd']==4
    assert xs[1].values['delta']==-6
    assert xs[1].values['cvd']==-2

def test_labels_use_strictly_future_bars():
    ys=build_labels(bars(5),horizons=(2,))
    y=ys[0]
    assert y.timestamp==0 and y.horizon_bars==2
    assert y.future_return==102/100-1
    assert y.mfe==103/100-1
    assert y.mae==100/100-1


def test_features_include_causal_multi_horizon_family():
    rows=build_feature_rows(bars(80))
    values=rows[-1].values
    for name in ('return_15','return_30','return_60','realized_vol_5','realized_vol_20',
                 'realized_vol_60','vol_ratio_5_20','volume_z20','range_z20',
                 'price_vs_sma5','price_vs_sma20','price_vs_sma60','sma5_vs_sma20',
                 'sma20_vs_sma60','body_pct','upper_wick_pct','lower_wick_pct'):
        assert name in values
        assert isinstance(values[name],float)
