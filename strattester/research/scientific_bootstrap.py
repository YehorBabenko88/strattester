"""Historical scientific bootstrap exported for Bybit Cluster Grid.

Uses only historically available datasets. L2/liquidations are explicitly absent.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import json,hashlib,time
from strattester.engine.executor import _coverage_ready
from .volatility import VolatilityObservatory
from .orderflow import cumulative_delta
from .volume_profile import proxy_profile
from .smc import market_structure
from .scalp_bootstrap import historical_scalp_events
from .scientific_graph import ScientificGraph,observation_artifact,volatility_artifact,nonlinear_evidence_artifact,regime_artifact

HISTORICAL_CAPABILITIES={
    "candles":False,
    "mark_price":False,
    "index_price":False,
    "premium_index":False,
    "open_interest":False,
    "funding":False,
    "long_short_ratio":False,
    "public_trade_aggregates":False,
    "true_l2_orderbook":False,
    "liquidations":False,
    "true_l2_absorption":False,
}
DATASETS={'candles':('1m',60000),'mark_price':('1m',60000),
          'index_price':('1m',60000),'premium_index':('1m',60000),
          'open_interest':('5m',300000),'funding':('480m',28800000),
          'long_short_ratio':('5m',300000),'public_trade_aggregates':('1m',60000)}


def dataset_evidence(store,symbol,start_ms,end_ms):
    """Local byte/coverage evidence; never an exchange-origin attestation.

    Funding/trade events have no completeness contract in the current store. Counting
    a sparse event table cannot establish its expected historical universe.
    """
    evidence={}
    for dataset,(timeframe,step) in DATASETS.items():
        lower=((start_ms+step-1)//step)*step
        upper=(end_ms//step)*step
        if dataset=='funding':lower,upper=start_ms,end_ms
        cov=store.coverage(symbol,dataset,timeframe,step_ms=step,start_ms=lower,end_ms=upper)
        fingerprint=store.range_fingerprint(SimpleNamespace(symbol=symbol,dataset=dataset,
                    timeframe=timeframe,start_ms=lower,end_ms=upper))
        event_history=dataset in ('funding','public_trade_aggregates')
        complete=(not event_history and lower<=upper and
                  _coverage_ready(store,symbol,dataset,timeframe,lower,upper,1,min(int(time.time()*1000),end_ms+60000)))
        evidence[dataset]={**fingerprint,'count':cov.count,'earliest':cov.earliest,
            'latest':cov.latest,'gaps':[asdict(gap) for gap in cov.gaps],
            'coverage_complete':complete,'provenance':'LOCAL_STORED_ROWS_NOT_EXCHANGE_ATTESTATION',
            'reason':('EVENT_HISTORY_CONTRACT_UNAVAILABLE' if event_history else
                      'EXACT_CLOSED_GRID' if complete else 'MISSING_INVALID_OR_INCOMPLETE_COVERAGE')}
    return evidence

def _bars(store,symbol,start_ms=None,end_ms=None):
    return [{"t":x.open_time,"open":x.open,"high":x.high,"low":x.low,"close":x.close,
             "volume":x.volume,"turnover":x.turnover or 0.0}
            for x in store.iter_candles(symbol,"1m",start_ms=start_ms,end_ms=end_ms)]

def _trade_aggs(store,symbol,start_ms=None,end_ms=None):
    return list(store.iter_public_trade_aggregates(symbol,"1m",start_ms=start_ms,end_ms=end_ms))

def build_symbol_science(store,symbol,start_ms=None,end_ms=None):
    requirements=[SimpleNamespace(dataset=dataset,timeframe=tf,start_ms=start_ms,end_ms=end_ms,required=True)
                  for dataset,(tf,_) in DATASETS.items()]
    with store.research_snapshot(symbol,requirements) as snapshot:
        return _build_symbol_science(snapshot,symbol,start_ms,end_ms)


def _build_symbol_science(store,symbol,start_ms=None,end_ms=None):
    bars=_bars(store,symbol,start_ms,end_ms)
    lower=start_ms if start_ms is not None else (bars[0]['t'] if bars else 0)
    upper=end_ms if end_ms is not None else (bars[-1]['t'] if bars else lower)
    evidence=dataset_evidence(store,symbol,lower,upper)
    common={'symbol':symbol,'samples':len(bars),'dataset_evidence':evidence,
            'live_promotion_allowed':False}
    if len(bars)<41:return {**common,"status":"INSUFFICIENT"}
    if not evidence['candles']['coverage_complete']:
        return {**common,'status':'PARTIAL','reason':'CANDLE_COVERAGE_INCOMPLETE'}
    trades=_trade_aggs(store,symbol,start_ms,end_ms)
    vol=VolatilityObservatory(window=20,percentile_lookback=252).snapshots(bars,bar_ms=60000)
    flow=cumulative_delta(trades) if trades else ()
    smc=market_structure(bars,bar_ms=60000)
    scalp=historical_scalp_events(bars,trades,symbol=symbol,bar_ms=60000)
    poc=None
    try:poc=asdict(proxy_profile(bars,known_at=bars[-1]["t"]))
    except ValueError:pass
    returns=[]
    for a,b in zip(bars,bars[1:]):
        returns.append((b["close"]/a["close"]-1.0) if a["close"] else 0.0)
    def mean(xs):return sum(xs)/len(xs) if xs else 0.0
    delta=[float(x.get("delta",0)) for x in flow]
    graph=ScientificGraph()
    obs=graph.add(observation_artifact(returns))
    vol_model=graph.add(volatility_artifact(obs,returns))
    nonlinear=graph.add(nonlinear_evidence_artifact(obs,returns))
    regime=graph.add(regime_artifact(vol_model,nonlinear))
    return {
      **common,"status":"READY" if all(x['coverage_complete'] for x in evidence.values()) else "PARTIAL",
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
      "scientific_layers":[{"id":x.artifact_id,"method":x.method,"layer":x.layer,"inputs":x.inputs,"payload":dict(x.payload),"confidence":x.confidence,"warnings":x.warnings} for x in graph.artifacts()],
      "features":{
        "volatility":[asdict(x) for x in vol[-512:]],
        "orderflow":[dict(x) for x in flow[-1024:]],
        "smc":[asdict(x) for x in smc[-512:]],
        "scalp_events":scalp[-2048:],
      },
    }

def export_scientific_bootstrap(store,symbols,out_path,start_ms=None,end_ms=None,source_id="strattester"):
    symbols=list(dict.fromkeys(str(s).upper() for s in symbols))
    rows=[build_symbol_science(store,s,start_ms,end_ms) for s in symbols]
    capabilities=dict(HISTORICAL_CAPABILITIES)
    for dataset in DATASETS:
        capabilities[dataset]=bool(rows) and all(r['dataset_evidence'][dataset]['coverage_complete'] for r in rows)
    payload={
      "schema":1,
      "source":source_id,
      "created_at":time.time(),
      "capabilities":capabilities,
      "status":"READY" if rows and all(r['status']=='READY' for r in rows) else "PARTIAL" if rows else "BLOCKED",
      "live_promotion_allowed":False,
      "research_scope":"HISTORICAL_BOOTSTRAP_ONLY",
      "symbols":rows,
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["sha256"]=hashlib.sha256(raw.encode()).hexdigest()
    p=Path(out_path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(payload,sort_keys=True,indent=2,default=str),encoding="utf-8")
    return payload
