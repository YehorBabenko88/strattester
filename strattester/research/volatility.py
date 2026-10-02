from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from statistics import mean

class VolatilityRegime(str, Enum):
    VERY_LOW='VERY_LOW'
    LOW='LOW'
    NORMAL='NORMAL'
    HIGH='HIGH'
    EXTREME='EXTREME'

@dataclass(frozen=True)
class VolatilitySnapshot:
    event_time:int
    known_at:int
    atr_pct:float
    realized_vol:float
    parkinson_vol:float
    range_pct:float
    volume_expansion:float
    turnover_expansion:float
    percentile:float
    regime:VolatilityRegime
    version:str

def _regime(percentile:float)->VolatilityRegime:
    if percentile <= .20: return VolatilityRegime.VERY_LOW
    if percentile <= .40: return VolatilityRegime.LOW
    if percentile <= .60: return VolatilityRegime.NORMAL
    if percentile <= .80: return VolatilityRegime.HIGH
    return VolatilityRegime.EXTREME

class VolatilityObservatory:
    def __init__(self,*,window:int=20,percentile_lookback:int=252,version:str='vol-v1'):
        if window < 2: raise ValueError('window must be >= 2')
        if percentile_lookback < 1: raise ValueError('percentile_lookback must be >= 1')
        self.window=window
        self.percentile_lookback=percentile_lookback
        self.version=version

    def snapshots(self,bars,*,bar_ms:int)->tuple[VolatilitySnapshot,...]:
        rows=list(bars)
        if len(rows) < self.window: return ()
        atr_history=[]
        out=[]
        true_ranges=[]
        log_returns=[]
        park_terms=[]
        for i,b in enumerate(rows):
            prev_close=rows[i-1]['close'] if i else b['open']
            tr=max(b['high']-b['low'],abs(b['high']-prev_close),abs(b['low']-prev_close))
            true_ranges.append(tr)
            if i:
                if b['close']>0 and prev_close>0:
                    log_returns.append(math.log(b['close']/prev_close))
                else:
                    log_returns.append(0.0)
            else:
                log_returns.append(0.0)
            if b['high']>0 and b['low']>0:
                park_terms.append(math.log(b['high']/b['low'])**2)
            else:
                park_terms.append(0.0)
            if i+1 < self.window:
                continue
            start=i+1-self.window
            window_rows=rows[start:i+1]
            close=b['close']
            atr=mean(true_ranges[start:i+1])
            atr_pct=atr/close if close else 0.0
            rets=log_returns[start:i+1]
            realized=math.sqrt(sum(x*x for x in rets)/len(rets))
            pterms=park_terms[start:i+1]
            parkinson=math.sqrt(sum(pterms)/(4*math.log(2)*len(pterms)))
            high=max(x['high'] for x in window_rows)
            low=min(x['low'] for x in window_rows)
            range_pct=(high-low)/close if close else 0.0
            current_volume=float(b.get('volume') or 0.0)
            prior_vol=[float(x.get('volume') or 0.0) for x in window_rows[:-1]]
            volume_base=mean(prior_vol) if prior_vol else 0.0
            volume_exp=current_volume/volume_base if volume_base>0 else 1.0
            current_turn=float(b.get('turnover') or 0.0)
            prior_turn=[float(x.get('turnover') or 0.0) for x in window_rows[:-1]]
            turnover_base=mean(prior_turn) if prior_turn else 0.0
            turnover_exp=current_turn/turnover_base if turnover_base>0 else 1.0
            prior=atr_history[-self.percentile_lookback:]
            percentile=(sum(x<=atr_pct for x in prior)/len(prior)) if prior else .5
            snap=VolatilitySnapshot(
                event_time=b['t'],known_at=b['t']+bar_ms,atr_pct=atr_pct,
                realized_vol=realized,parkinson_vol=parkinson,range_pct=range_pct,
                volume_expansion=volume_exp,turnover_expansion=turnover_exp,
                percentile=percentile,regime=_regime(percentile),version=self.version)
            out.append(snap)
            atr_history.append(atr_pct)
        return tuple(out)
