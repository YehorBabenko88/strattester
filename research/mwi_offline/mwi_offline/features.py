"""Versioned, bounded causal zone examples for standalone offline research only.

Protocol TOY_NEAR_ZONE_V2: 48 prior contiguous bars, 14-bar ATR, frozen extrema;
width=.15*ATR (>=.02), barriers=.8*ATR (>=.04), future full bars only.
Touch means a bar range intersects the frozen zone after an approach; close may
lie outside its width, but strictly between the outer barriers. This is the
broader NEAR-ZONE cohort, not the narrower within-zone-close proposal.
No data source authentication, execution or training admission is provided.
"""
import hashlib
import json
import math
from collections import Counter

MINUTE=60000
LOOKBACK=48
BASELINE=["side","signed_distance_atr","return_1","return_6","atr_fraction","volume_ratio","range_atr","level_width_atr"]
EXTRAS=["nearest_other_level_atr","confluence_fraction","mean_degree","mean_edge_distance_atr","node_count_scaled"]
FIELDS={"symbol","open_ms","end_ms","available_ms","open","high","low","close","volume"}


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _validate(bars):
    if not isinstance(bars,list) or len(bars)>10000:raise ValueError("BAR_BOUNDS")
    previous={}
    for b in bars:
        if type(b) is not dict or set(b)!=FIELDS:raise ValueError("BAR_SCHEMA")
        if type(b["symbol"]) is not str or not b["symbol"]:raise ValueError("SYMBOL")
        if any(type(b[k]) is not int or not 0<=b[k]<=2**53-1 for k in ("open_ms","end_ms","available_ms")):raise ValueError("CLOCK")
        if b["open_ms"]%MINUTE or b["end_ms"]!=b["open_ms"]+MINUTE or b["available_ms"]<b["end_ms"]:raise ValueError("CLOCK")
        if b["symbol"] in previous and b["open_ms"]<=previous[b["symbol"]]:raise ValueError("DUPLICATE_OR_ORDER")
        previous[b["symbol"]]=b["open_ms"]
        if any(type(b[k]) not in (float,int) or not math.isfinite(b[k]) for k in ("open","high","low","close","volume")):raise ValueError("NONFINITE")
        if not 0<b["low"]<=min(b["open"],b["close"])<=max(b["open"],b["close"])<=b["high"] or b["volume"]<0:raise ValueError("OHLCV")


def _atr(history):
    tail=history[-15:]
    return sum(max(b["high"]-b["low"],abs(b["high"]-a["close"]),abs(b["low"]-a["close"])) for a,b in zip(tail,tail[1:]))/14


def _graph(history,level,atr,width):
    # Candidate nodes exist before the touch. IDs encode event time and side.
    nodes=[(b["end_ms"],s,b[k]) for b in history[-24:] for s,k in ((-1,"low"),(1,"high"))]
    nodes=sorted(nodes)[:64]
    edges=set()
    for i,(_,_,p) in enumerate(nodes):
        nearest=sorted((abs(p-q),j) for j,(_,_,q) in enumerate(nodes) if j!=i)[:4]
        for _,j in nearest:edges.add(tuple(sorted((i,j))))
    edges=sorted(edges)[:1024]
    distances=[abs(nodes[i][2]-nodes[j][2])/atr for i,j in edges]
    extras=[min(abs(p-level)/atr for _,_,p in nodes),
            sum(abs(p-level)<=width for _,_,p in nodes)/len(nodes),
            2*len(edges)/len(nodes),sum(distances)/len(distances),len(nodes)/64]
    return nodes,edges,extras


def _outcome(future,direction,level,barrier):
    for b in future:
        upper=b["high"]>=level+barrier
        lower=b["low"]<=level-barrier
        if upper and lower:return "AMBIGUOUS"
        if upper:return "BREAKOUT" if direction==1 else "BOUNCE"
        if lower:return "BOUNCE" if direction==1 else "BREAKOUT"
    return "TIMEOUT"


def build_examples(bars,horizon=12):
    _validate(bars)
    if type(horizon) is not int or not 1<=horizon<=120:raise ValueError("HORIZON")
    counts=Counter({k:0 for k in ("BREAKOUT","BOUNCE","TIMEOUT","AMBIGUOUS","UNOBSERVABLE","PENDING","SUPPRESSED","NO_CAUSAL_HISTORY","ALREADY_RESOLVED")})
    examples=[]
    symbols={b["symbol"] for b in bars}
    for symbol in sorted(symbols):
        series=[b for b in bars if b["symbol"]==symbol]
        by_open={b["open_ms"]:b for b in series}
        until=-1
        for i in range(LOOKBACK,len(series)):
            touch=series[i]
            if touch["end_ms"]<=until:
                counts["SUPPRESSED"]+=1
                continue
            prior=series[i-LOOKBACK:i]
            # Levels must pre-exist the entire touch bar, not merely its decision.
            if any(b["available_ms"]>touch["open_ms"] for b in prior) or any(a["end_ms"]!=b["open_ms"] for a,b in zip(prior,prior[1:])) or prior[-1]["end_ms"]!=touch["open_ms"]:
                counts["NO_CAUSAL_HISTORY"]+=1
                continue
            atr=_atr(prior)
            if atr<=0:continue
            width=max(.02,.15*atr);barrier=max(.04,.8*atr)
            candidates=[]
            for direction,level in ((1,max(b["high"] for b in prior)),(-1,min(b["low"] for b in prior))):
                if touch["low"]<=level+width and touch["high"]>=level-width and direction*(prior[-1]["close"]-level)<-width:
                    candidates.append((abs(prior[-1]["close"]-level),direction,level))
            if not candidates:continue
            _,direction,level=min(candidates)
            if abs(touch["close"]-level)>=barrier:
                counts["ALREADY_RESOLVED"]+=1
                continue
            cutoff=touch["available_ms"]
            future_start=((cutoff+MINUTE-1)//MINUTE)*MINUTE
            label_end=future_start+horizon*MINUTE
            until=label_end
            future=[by_open.get(future_start+j*MINUTE) for j in range(horizon)]
            if label_end>series[-1]["end_ms"]:
                counts["PENDING"]+=1
                continue
            if any(b is None for b in future):
                counts["UNOBSERVABLE"]+=1
                continue
            label=_outcome(future,direction,level,barrier)
            counts[label]+=1
            if label=="AMBIGUOUS":continue
            baseline=[direction,direction*(touch["close"]-level)/atr,
                      touch["close"]/prior[-1]["close"]-1,touch["close"]/prior[-6]["close"]-1,
                      atr/touch["close"],touch["volume"]/max(sum(b["volume"] for b in prior)/LOOKBACK,1e-12),
                      (touch["high"]-touch["low"])/atr,width/atr]
            nodes,edges,extra=_graph(prior,level,atr,width)
            state=dict(protocol="TOY_NEAR_ZONE_V2",symbol=symbol,cutoff=cutoff,history=prior,touch=touch,
                       direction=direction,level=level,width=width,barrier=barrier,baseline=baseline,nodes=nodes,edges=edges)
            ident=symbol+":"+str(cutoff)
            examples.append(dict(id=ident,cutoff=cutoff,label_end=label_end,
                                 label_available=max(b["available_ms"] for b in future),label=label,
                                 group_id=ident,baseline=baseline,node_only=baseline+extra[:2]+extra[-1:],graph=baseline+extra,state_hash=_hash(state)))
    examples.sort(key=lambda r:(r["cutoff"],r["id"]))
    counts["ELIGIBLE"]=len(examples)
    counts["BARS"]=len(bars)
    return dict(examples=examples,counts=dict(counts),feature_names=dict(baseline=list(BASELINE),node_only=list(BASELINE+EXTRAS[:2]+EXTRAS[-1:]),graph=list(BASELINE+EXTRAS)))
