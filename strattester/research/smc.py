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


def market_structure(bars,*,bar_ms:int,left:int=2,right:int=2,version='smc-v1'):
    swings=confirmed_swings(bars,left=left,right=right,version=version)
    out=list(swings)
    highs=[s for s in swings if s.kind=='swing_high']
    lows=[s for s in swings if s.kind=='swing_low']
    trend=None
    for i,b in enumerate(bars):
        close_known=b['t']+bar_ms
        visible_highs=[s for s in highs if s.known_at<=b['t']]
        visible_lows=[s for s in lows if s.known_at<=b['t']]
        if visible_highs:
            level=visible_highs[-1]
            if b['high']>level.value and b.get('close',b['high'])<=level.value:
                out.append(CausalFeature(b['t'],close_known,'bearish_liquidity_sweep',{'level':level.value},version))
            elif b.get('close',b['high'])>level.value:
                kind='bullish_choch' if trend=='bearish' else 'bullish_bos'
                out.append(CausalFeature(b['t'],close_known,kind,{'level':level.value},version)); trend='bullish'
                for prior in reversed(bars[:i]):
                    if prior.get('close',0)<prior.get('open',0):
                        out.append(CausalFeature(prior['t'],close_known,'bullish_order_block',{'low':prior['low'],'high':prior['high']},version)); break
        if visible_lows:
            level=visible_lows[-1]
            if b['low']<level.value and b.get('close',b['low'])>=level.value:
                out.append(CausalFeature(b['t'],close_known,'bullish_liquidity_sweep',{'level':level.value},version))
            elif b.get('close',b['low'])<level.value:
                kind='bearish_choch' if trend=='bullish' else 'bearish_bos'
                out.append(CausalFeature(b['t'],close_known,kind,{'level':level.value},version)); trend='bearish'
                for prior in reversed(bars[:i]):
                    if prior.get('close',0)>prior.get('open',0):
                        out.append(CausalFeature(prior['t'],close_known,'bearish_order_block',{'low':prior['low'],'high':prior['high']},version)); break
    return tuple(sorted(out,key=lambda x:(x.known_at,x.event_time,x.kind)))
