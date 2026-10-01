from .causal import CausalFeature

def confirmed_swings(bars,*,left:int=2,right:int=2,version='smc-v1'):
    out=[]
    for i in range(left,len(bars)-right):
        b=bars[i]; l=bars[i-left:i]; r=bars[i+1:i+1+right]
        known=r[-1]['t']
        if all(b['high']>x['high'] for x in l+r): out.append(CausalFeature(b['t'],known,'swing_high',b['high'],version))
        if all(b['low']<x['low'] for x in l+r): out.append(CausalFeature(b['t'],known,'swing_low',b['low'],version))
    return tuple(out)

def fair_value_gaps(bars,*,bar_ms:int,version='smc-v1'):
    out=[]
    for i in range(2,len(bars)):
        a,c=bars[i-2],bars[i]
        if c['low']>a['high']:
            out.append(CausalFeature(c['t'],c['t']+bar_ms,'bullish_fvg',{'low':a['high'],'high':c['low']},version))
        elif c['high']<a['low']:
            out.append(CausalFeature(c['t'],c['t']+bar_ms,'bearish_fvg',{'low':c['high'],'high':a['low']},version))
    return tuple(out)
