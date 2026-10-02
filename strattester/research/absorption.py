from dataclasses import dataclass
from .orderflow import cumulative_delta,aggression_decay

@dataclass(frozen=True)
class AbsorptionConfig:
    min_sell_volume:float=20.0
    min_buy_volume:float=20.0
    max_penetration_ticks:float=2.0
    aggression_window:int=3
    entry_offset_ticks:float=1.0

@dataclass(frozen=True)
class AbsorptionSetup:
    direction:str
    level:float
    known_at:int
    entry_price:float
    cvd:float
    aggressive_volume:float
    mode:str='ABSORPTION_PROXY'

def detect_absorption_setup(rows,*,level:float,tick_size:float,direction:str,config:AbsorptionConfig=AbsorptionConfig()):
    xs=list(rows)
    if len(xs)<config.aggression_window:return None
    xs=xs[-config.aggression_window:]
    cvd=cumulative_delta(xs)
    prices=[float(x['price']) for x in xs]
    if direction=='long':
        aggressive=sum(float(x.get('sell_volume',0)) for x in xs)
        if aggressive<config.min_sell_volume:return None
        if min(prices)<level-config.max_penetration_ticks*tick_size:return None
        decay=aggression_decay(xs,side='sell',window=config.aggression_window)
        if not decay or not decay['decaying']:return None
        if cvd[-1]['cvd']<=cvd[-2]['cvd']:return None
        if prices[-1]<prices[-2]:return None
        entry=level+config.entry_offset_ticks*tick_size
    elif direction=='short':
        aggressive=sum(float(x.get('buy_volume',0)) for x in xs)
        if aggressive<config.min_buy_volume:return None
        if max(prices)>level+config.max_penetration_ticks*tick_size:return None
        decay=aggression_decay(xs,side='buy',window=config.aggression_window)
        if not decay or not decay['decaying']:return None
        if cvd[-1]['cvd']>=cvd[-2]['cvd']:return None
        if prices[-1]>prices[-2]:return None
        entry=level-config.entry_offset_ticks*tick_size
    else: raise ValueError('direction')
    return AbsorptionSetup(direction,float(level),int(xs[-1]['t']),float(entry),float(cvd[-1]['cvd']),aggressive)
