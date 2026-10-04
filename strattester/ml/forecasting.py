from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

class ForecastProvider(Protocol):
    def forecast_features(self, history:list[dict], *, horizon:int)->dict[str,float]: ...

@dataclass(frozen=True)
class NullForecastProvider:
    def forecast_features(self, history, *, horizon):
        return {}

def attach_forecast_features(rows, bars, provider:ForecastProvider|None, *, horizon=15):
    if provider is None:return tuple(rows)
    bars=sorted((dict(x) for x in bars),key=lambda x:int(x['t']))
    by_t={int(x['t']):i for i,x in enumerate(bars)}
    out=[]
    for row in rows:
        idx=by_t.get(int(row.timestamp))
        if idx is None:continue
        extra=provider.forecast_features(bars[:idx+1],horizon=int(horizon))
        values=dict(row.values)
        for k,v in (extra or {}).items():
            values[f'forecast_{k}']=float(v)
        out.append(type(row)(row.timestamp,row.known_at,values,row.regime))
    return tuple(out)
