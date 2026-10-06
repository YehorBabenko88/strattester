"""Historical scientific bootstrap exported for Bybit Cluster Grid.

Uses only historically available datasets. L2/liquidations are explicitly absent.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import json,hashlib,time
from .volatility import VolatilityObservatory
from .orderflow import cumulative_delta
from .volume_profile import proxy_profile
from .smc import market_structure

HISTORICAL_CAPABILITIES={
    "candles":True,
    "mark_price":True,
    "index_price":True,
    "premium_index":True,
    "open_interest":True,
    "funding":True,
    "long_short_ratio":True,
    "public_trade_aggregates":True,
    "true_l2_orderbook":False,
    "liquidations":False,
    "true_l2_absorption":False,
}

def _bars(store,symbol,start_ms=None,end_ms=None):
    return [{"t":x.open_time,"open":x.open,"high":x.high,"low":x.low,"close":x.close,
             "volume":x.volume,"turnover":x.turnover or 0.0}
            for x in store.iter_candles(symbol,"1m",start_ms=start_ms,end_ms=end_ms)]

def _trade_aggs(store,symbol,start_ms=None,end_ms=None):
    return list(store.iter_public_trade_aggregates(symbol,"1m",start_ms=start_ms,end_ms=end_ms))

def build_symbol_science(store,symbol,start_ms=None,end_ms=None):
    bars=_bars(store,symbol,start_ms,end_ms)
    if len(bars)<30:return {"symbol":symbol,"status":"INSUFFICIENT","samples":len(bars)}
    trades=_trade_aggs(store,symbol,start_ms,end_ms)
    vol=VolatilityObservatory(window=20,percentile_lookback=252).snapshots(bars,bar_ms=60000)
    flow=cumulative_delta(trades) if trades else ()
    smc=market_structure(bars,bar_ms=60000)
    poc=None
    try:poc=asdict(proxy_profile(bars,known_at=bars[-1]["t"]))
    except ValueError:pass
    returns=[]
    for a,b in zip(bars,bars[1:]):
        returns.append((b["close"]/a["close"]-1.0) if a["close"] else 0.0)
    def mean(xs):return sum(xs)/len(xs) if xs else 0.0
    delta=[float(x.get("delta",0)) for x in flow]
    return {
      "symbol":symbol,"status":"READY","samples":len(bars),
      "from_ms":bars[0]["t"],"through_ms":bars[-1]["t"],
      "summary":{
        "mean_return":mean(returns),
        "mean_abs_return":mean([abs(x) for x in returns]),
        "volatility_regimes":{k:sum(1 for x in vol if x.regime.value==k) for k in
          ("VERY_LOW","LOW","NORMAL","HIGH","EXTREME")},
        "mean_delta":mean(delta),
        "smc_events":len(smc),
        "latest_poc_proxy":poc,
      },
      "features":{
        "volatility":[asdict(x) for x in vol[-512:]],
        "orderflow":[dict(x) for x in flow[-1024:]],
        "smc":[asdict(x) for x in smc[-512:]],
      },
    }

def export_scientific_bootstrap(store,symbols,out_path,start_ms=None,end_ms=None,source_id="strattester"):
    rows=[build_symbol_science(store,str(s).upper(),start_ms,end_ms) for s in symbols]
    payload={
      "schema":1,
      "source":source_id,
      "created_at":time.time(),
      "capabilities":HISTORICAL_CAPABILITIES,
      "research_scope":"HISTORICAL_BOOTSTRAP_ONLY",
      "symbols":rows,
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["sha256"]=hashlib.sha256(raw.encode()).hexdigest()
    p=Path(out_path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(payload,sort_keys=True,indent=2,default=str),encoding="utf-8")
    return payload
