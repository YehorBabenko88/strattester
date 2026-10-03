from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class FeatureRow:
    timestamp:int
    known_at:int
    values:dict[str,float]
    regime:str

def _mean(xs):
    return sum(xs)/len(xs) if xs else 0.0

def _std(xs):
    if len(xs)<2:return 0.0
    m=_mean(xs)
    return sqrt(sum((x-m)**2 for x in xs)/len(xs))

def classify_regime(returns, ranges):
    if not returns:return 'UNKNOWN'
    rv=_std(returns[-20:])
    recent=abs(returns[-1])
    baseline=_mean([abs(x) for x in returns[-20:]]) or 1e-12
    range_now=ranges[-1] if ranges else 0.0
    range_base=_mean(ranges[-20:]) or 1e-12
    if recent>3*baseline or range_now>2.5*range_base:return 'EXTREME'
    if rv and recent>1.5*baseline:return 'EXPANSION'
    if recent<0.5*baseline and range_now<0.7*range_base:return 'COMPRESSION'
    if len(returns)>=4 and all(x>0 for x in returns[-3:]):return 'TREND_UP'
    if len(returns)>=4 and all(x<0 for x in returns[-3:]):return 'TREND_DOWN'
    return 'RANGE'

def build_feature_rows(bars, public_trade_aggregates=(), *, bar_ms=60_000, lookback=20):
    bars=sorted((dict(x) for x in bars),key=lambda x:int(x['t']))
    flow={int(x.get('open_time',x.get('t'))):x for x in public_trade_aggregates}
    out=[]; closes=[]; returns=[]; ranges=[]; volumes=[]; cvd=0.0
    for i,b in enumerate(bars):
        t=int(b['t']); close=float(b['close']); high=float(b['high']); low=float(b['low'])
        vol=float(b.get('volume',0.0)); turnover=float(b.get('turnover',0.0) or 0.0)
        prev=closes[-1] if closes else close
        ret=(close/prev-1.0) if prev else 0.0
        rng=(high-low)/prev if prev else 0.0
        closes.append(close); returns.append(ret); ranges.append(rng); volumes.append(vol)
        f=flow.get(t)
        delta=0.0; imbalance=0.0
        if f is not None:
            buy=float(f.get('buy_volume',0.0)); sell=float(f.get('sell_volume',0.0))
            delta=buy-sell; total=buy+sell; imbalance=delta/total if total else 0.0
            cvd+=delta
        hist=returns[max(0,len(returns)-lookback):]
        vh=volumes[max(0,len(volumes)-lookback):]
        rh=ranges[max(0,len(ranges)-lookback):]
        vmean=_mean(vh); rmean=_mean(rh)
        values={
            'return_1':ret,
            'return_3':sum(returns[-3:]),
            'return_5':sum(returns[-5:]),
            'realized_vol':_std(hist),
            'range_pct':rng,
            'range_expansion':rng/(rmean or 1e-12),
            'volume':vol,
            'volume_expansion':vol/(vmean or 1e-12),
            'turnover':turnover,
            'delta':delta,
            'delta_imbalance':imbalance,
            'cvd':cvd,
        }
        out.append(FeatureRow(t,t+bar_ms,values,classify_regime(hist,rh)))
    return tuple(out)
