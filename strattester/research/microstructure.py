from dataclasses import dataclass
from enum import Enum

class AbsorptionMode(str,Enum):
    ABSORPTION_PROXY='ABSORPTION_PROXY'
    ABSORPTION_L2='ABSORPTION_L2'

@dataclass(frozen=True)
class AbsorptionSignal:
    event_time:int; known_at:int; side:str; level:float; mode:AbsorptionMode
    buy_volume:float; sell_volume:float; cvd:float; max_penetration_ticks:float

@dataclass(frozen=True)
class SweepReversalSignal:
    event_time:int; known_at:int; side:str; level:float; sweep_pct:float
    buy_volume:float; sell_volume:float; cvd:float

def _flow(trades,end):
    xs=[x for x in trades if x['t']<=end]
    buy=sum(float(x['size']) for x in xs if x['side']=='Buy')
    sell=sum(float(x['size']) for x in xs if x['side']=='Sell')
    return buy,sell,buy-sell

def detect_absorption_proxy(trades,*,level:float,tick_size:float,known_at:int,min_aggressive_volume:float,max_penetration_ticks:float=2,lookback_ms:int=5_000):
    start=known_at-lookback_ms
    xs=[x for x in trades if start<=x['t']<=known_at]
    if not xs or tick_size<=0:return None
    buy,sell,cvd=_flow(xs,known_at)
    penetration=max(0.0,(level-min(float(x['price']) for x in xs))/tick_size)
    if sell<min_aggressive_volume or penetration>max_penetration_ticks:return None
    if float(xs[-1]['price']) < level-max_penetration_ticks*tick_size:return None
    return AbsorptionSignal(xs[-1]['t'],known_at,'long',level,AbsorptionMode.ABSORPTION_PROXY,buy,sell,cvd,penetration)

def detect_liquidity_sweep_reversal(bars,trades,*,level:float,direction:str,bar_ms:int,min_sweep_pct:float=.0015,max_sweep_pct:float=.004):
    if not bars:return None
    b=bars[-1]; known=b['t']+bar_ms
    buy,sell,cvd=_flow([x for x in trades if b['t']<=x['t']<=known],known)
    if direction=='short':
        sweep=(float(b['high'])-level)/level
        if not(min_sweep_pct<=sweep<=max_sweep_pct) or float(b['close'])>=level or sell<=buy:return None
        side='short'
    elif direction=='long':
        sweep=(level-float(b['low']))/level
        if not(min_sweep_pct<=sweep<=max_sweep_pct) or float(b['close'])<=level or buy<=sell:return None
        side='long'
    else: raise ValueError('direction')
    return SweepReversalSignal(b['t'],known,side,level,sweep,buy,sell,cvd)
