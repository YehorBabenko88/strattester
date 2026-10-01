from .causal import CausalFeature

def completed_period_levels(bars,*,period_ms:int,next_bar_ms:int,version='levels-v1'):
    groups={}
    for b in bars: groups.setdefault((b['t']//period_ms)*period_ms,[]).append(b)
    out=[]
    for start,rows in sorted(groups.items()):
        period_end=start+period_ms
        hi=max(rows,key=lambda x:x['high']); lo=min(rows,key=lambda x:x['low'])
        out.append(CausalFeature(hi['t'],period_end,'period_high',hi['high'],version))
        out.append(CausalFeature(lo['t'],period_end,'period_low',lo['low'],version))
    return tuple(out)
