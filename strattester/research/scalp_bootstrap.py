"""Historical scalp-event adapter matching the Grid scalp ontology contract."""
from __future__ import annotations
from dataclasses import asdict
from .volatility import VolatilityObservatory
from .orderflow import cumulative_delta
from .smc import market_structure

SCHEMA="scalp-ontology-v1"

def _nearest_level(events,bar):
    candidates=[]
    for e in events:
        if e.known_at>bar["t"]:continue
        if e.kind in ("swing_high","swing_low"):
            candidates.append((abs(float(bar["close"])-float(e.value)),e.kind,float(e.value)))
        elif e.kind.endswith("_order_block") and isinstance(e.value,dict):
            lo=float(e.value["low"]);hi=float(e.value["high"]);mid=(lo+hi)/2
            candidates.append((abs(float(bar["close"])-mid),e.kind,mid))
    return min(candidates) if candidates else None

def historical_scalp_events(bars,trade_aggregates=(),*,symbol,bar_ms=60000):
    rows=list(bars);trades=list(trade_aggregates)
    if len(rows)<30:return []
    vol=VolatilityObservatory(window=20,percentile_lookback=252).snapshots(rows,bar_ms=bar_ms)
    vol_by_t={x.event_time:x for x in vol}
    flow={x["t"]:x for x in cumulative_delta(trades)} if trades else {}
    smc=market_structure(rows,bar_ms=bar_ms)
    out=[]
    prior_volume=[]
    for i,b in enumerate(rows):
        if i<20:prior_volume.append(float(b.get("volume") or 0));continue
        lvl=_nearest_level(smc,b)
        prior=prior_volume[-20:];base=sum(prior)/len(prior) if prior else 0
        vexp=float(b.get("volume") or 0)/base if base>0 else 1.0
        prior_volume.append(float(b.get("volume") or 0))
        if lvl is None:continue
        dist,kind,price=lvl
        dist_bps=dist/max(float(b["close"]),1e-12)*10000
        if dist_bps>25:continue
        direction=1 if price>=float(b["close"]) else -1
        ret=((rows[i+1]["close"]/b["close"])-1)*10000 if i+1<len(rows) and b["close"] else None
        f=flow.get(b["t"]) or {}
        vr=vol_by_t.get(b["t"])
        state="LEVEL_APPROACH"
        if vexp>=1.8:state="IMPULSE_BUILDUP"
        if ret is not None and abs(ret)>=8:
            state="BREAKOUT" if ret*direction>0 else "REJECTION"
        out.append({
          "schema":SCHEMA,"symbol":symbol,"event_ts_ms":int(b["t"]),"known_at_ms":int(b["t"]+bar_ms),
          "level_kind":kind,"level_price":price,"direction":direction,"state":state,
          "features":{
            "level_distance_bps":dist_bps,
            "volatility_regime":vr.regime.value if vr else "UNKNOWN",
            "volume_expansion":vexp,
            "turnover_expansion":vr.turnover_expansion if vr else None,
            "delta_ratio":((float(f.get("buy_volume",0))-float(f.get("sell_volume",0)))/
                           max(float(f.get("buy_volume",0))+float(f.get("sell_volume",0)),1e-12)) if f else None,
            "cvd_slope":float(f.get("cvd",0)) if f else None,
            "open_interest_rate":None,"funding_rate":None,"long_short_ratio":None,
            "tape_speed":None,"large_trade_ratio":None,
            "book_imbalance":None,"book_velocity":None,"cancel_rate":None,
            "wall_ratio":None,"wall_replenishment":None,"spread_bps":None,
          },
          "outcome":{"next_1m_return_bps":ret},
          "capability_scope":"HISTORICAL_NO_L2",
        })
    return out
