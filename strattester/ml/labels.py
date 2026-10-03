from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LabelRow:
    timestamp:int
    horizon_bars:int
    future_return:float
    mfe:float
    mae:float
    up:int

def build_labels(bars, *, horizons=(5,15,60)):
    bars=sorted((dict(x) for x in bars),key=lambda x:int(x['t']))
    out=[]
    for i,b in enumerate(bars):
        entry=float(b['close'])
        if entry<=0:continue
        for h in horizons:
            j=i+int(h)
            if j>=len(bars):continue
            window=bars[i+1:j+1]
            future=float(bars[j]['close'])/entry-1.0
            mfe=max(float(x['high'])/entry-1.0 for x in window)
            mae=min(float(x['low'])/entry-1.0 for x in window)
            out.append(LabelRow(int(b['t']),int(h),future,mfe,mae,1 if future>0 else 0))
    return tuple(out)
