from dataclasses import dataclass
from .causal import CausalFeature

def confirmed_swings(bars,*,left:int=2,right:int=2,bar_ms:int,version='smc-v1'):
    out=[]
    for i in range(left,len(bars)-right):
        b=bars[i]; l=bars[i-left:i]; r=bars[i+1:i+1+right]
        known=r[-1]['t']+bar_ms
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
    swings=confirmed_swings(bars,left=left,right=right,bar_ms=bar_ms,version=version)
    out=list(swings)
    highs=[s for s in swings if s.kind=='swing_high']
    lows=[s for s in swings if s.kind=='swing_low']
    broken_highs=set(); broken_lows=set(); trend=None
    for i,b in enumerate(bars):
        close_known=b['t']+bar_ms
        visible_highs=[s for s in highs if s.known_at<=b['t']]
        visible_lows=[s for s in lows if s.known_at<=b['t']]
        if visible_highs:
            level=visible_highs[-1]
            key=(level.event_time,level.value)
            if key not in broken_highs:
                if b['high']>level.value and b.get('close',b['high'])<=level.value:
                    out.append(CausalFeature(b['t'],close_known,'bearish_liquidity_sweep',{'level':level.value,'swing_time':level.event_time},version))
                elif b.get('close',b['high'])>level.value:
                    kind='bullish_choch' if trend=='bearish' else 'bullish_bos'
                    out.append(CausalFeature(b['t'],close_known,kind,{'level':level.value,'swing_time':level.event_time},version))
                    broken_highs.add(key); trend='bullish'
                    candidates=[x for x in bars[:i] if x['t']>=level.event_time and x.get('close',0)<x.get('open',0)]
                    if candidates:
                        prior=candidates[-1]
                        out.append(CausalFeature(prior['t'],close_known,'bullish_order_block',{'low':prior['low'],'high':prior['high'],'break_time':b['t']},version))
        if visible_lows:
            level=visible_lows[-1]
            key=(level.event_time,level.value)
            if key not in broken_lows:
                if b['low']<level.value and b.get('close',b['low'])>=level.value:
                    out.append(CausalFeature(b['t'],close_known,'bullish_liquidity_sweep',{'level':level.value,'swing_time':level.event_time},version))
                elif b.get('close',b['low'])<level.value:
                    kind='bearish_choch' if trend=='bullish' else 'bearish_bos'
                    out.append(CausalFeature(b['t'],close_known,kind,{'level':level.value,'swing_time':level.event_time},version))
                    broken_lows.add(key); trend='bearish'
                    candidates=[x for x in bars[:i] if x['t']>=level.event_time and x.get('close',0)>x.get('open',0)]
                    if candidates:
                        prior=candidates[-1]
                        out.append(CausalFeature(prior['t'],close_known,'bearish_order_block',{'low':prior['low'],'high':prior['high'],'break_time':b['t']},version))
    return tuple(sorted(out,key=lambda x:(x.known_at,x.event_time,x.kind)))


@dataclass(frozen=True)
class SMCEvent:
    event_time:int
    known_at:int
    kind:str
    value:object
    version:str
    timeframe:str

_TF_MS={'1m':60000,'3m':180000,'5m':300000,'15m':900000,'30m':1800000,'1h':3600000,'2h':7200000,'4h':14400000,'6h':21600000,'12h':43200000,'1d':86400000}

def build_mtf_structure(series_by_timeframe,*,left:int=2,right:int=2,version='smc-mtf-v1'):
    out=[]
    for tf,bars in series_by_timeframe.items():
        if tf not in _TF_MS: raise ValueError(f'unsupported timeframe: {tf}')
        for x in market_structure(bars,bar_ms=_TF_MS[tf],left=left,right=right,version=version):
            out.append(SMCEvent(x.event_time,x.known_at,x.kind,x.value,x.version,tf))
    return tuple(sorted(out,key=lambda x:(x.known_at,x.event_time,x.timeframe,x.kind)))

class SMCContext:
    def __init__(self,events): self.events=tuple(events)
    def bias_at(self,decision_time:int,timeframe:str):
        structural=[x for x in self.events if x.timeframe==timeframe and x.known_at<=decision_time and x.kind in ('bullish_bos','bearish_bos','bullish_choch','bearish_choch')]
        if not structural:return None
        return 'bullish' if structural[-1].kind.startswith('bullish') else 'bearish'
    def entry_allowed(self,decision_time:int,*,entry_timeframe:str,bias_timeframe:str,direction:str)->bool:
        if entry_timeframe not in _TF_MS or bias_timeframe not in _TF_MS:return False
        if _TF_MS[bias_timeframe]<=_TF_MS[entry_timeframe]:raise ValueError('bias timeframe must be higher than entry timeframe')
        return self.bias_at(decision_time,bias_timeframe)==direction
