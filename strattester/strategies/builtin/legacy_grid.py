from __future__ import annotations
from dataclasses import dataclass
from strattester.strategies.base import DataRequirement
@dataclass(frozen=True)
class BacktestConfig:
    position_usd:float=100.0
    entry_distance:float=0.005
    take_profit:float=0.015
    stop_loss:float=0.010
    taker_fee:float=0.00055
    max_entries_per_level:int|None=None
    allowed_level_types:tuple[str,...]=('HIGH','LOW')
    max_level_age_ms:int|None=None
    high_direction:str='LONG'
    low_direction:str='SHORT'
@dataclass(frozen=True)
class Trade:
    direction:str; entry:float; exit:float; gross_pnl:float; fees:float; net_pnl:float; reason:str
def close_trade(direction,entry,exit_price,reason,cfg=BacktestConfig()):
    qty=cfg.position_usd/entry
    gross=(exit_price-entry)*qty if direction=='LONG' else (entry-exit_price)*qty
    fees=(entry*qty+exit_price*qty)*cfg.taker_fee
    return Trade(direction,entry,exit_price,gross,fees,gross-fees,reason)
def legacy_variants():
    H=60*60*1000; D=24*H
    low=lambda **kw: BacktestConfig(allowed_level_types=('LOW',),**kw)
    high=lambda **kw: BacktestConfig(allowed_level_types=('HIGH',),**kw)
    return {
        'BASE':BacktestConfig(),
        'LOW_BASE':low(), 'LOW_FIRST_TOUCH':low(max_entries_per_level=1),
        'LOW_ENTRY_010':low(entry_distance=.001), 'LOW_ENTRY_025':low(entry_distance=.0025), 'LOW_ENTRY_040':low(entry_distance=.004),
        'LOW_TP20':low(entry_distance=.0025,take_profit=.020), 'LOW_TP25':low(entry_distance=.0025,take_profit=.025), 'LOW_SL075':low(entry_distance=.0025,stop_loss=.0075),
        'LOW_AGE_24H':low(max_level_age_ms=24*H), 'LOW_AGE_3D':low(max_level_age_ms=3*D), 'LOW_AGE_7D':low(max_level_age_ms=7*D), 'LOW_AGE_30D':low(max_level_age_ms=30*D),
        'HIGH_BASE':high(), 'HIGH_FIRST_TOUCH':high(max_entries_per_level=1),
        'HIGH_ENTRY_010':high(entry_distance=.001), 'HIGH_ENTRY_025':high(entry_distance=.0025), 'HIGH_ENTRY_040':high(entry_distance=.004),
        'HIGH_TP20':high(entry_distance=.0025,take_profit=.020), 'HIGH_TP25':high(entry_distance=.0025,take_profit=.025), 'HIGH_SL075':high(entry_distance=.0025,stop_loss=.0075),
        'HIGH_AGE_24H':high(max_level_age_ms=24*H), 'HIGH_AGE_3D':high(max_level_age_ms=3*D), 'HIGH_AGE_7D':high(max_level_age_ms=7*D), 'HIGH_AGE_30D':high(max_level_age_ms=30*D),
        'REVERSAL_BASE':BacktestConfig(high_direction='SHORT',low_direction='LONG'),
        'HIGH_SHORT':high(high_direction='SHORT'), 'LOW_LONG':low(low_direction='LONG'),
    }


import heapq, math
from typing import Optional, Dict, List, Tuple

@dataclass(frozen=True)
class MinuteCandle:
    ts:int; open:float; high:float; low:float; close:float; volume:float=0.0; turnover:float=0.0

@dataclass(frozen=True)
class LevelSeed:
    timeframe:str; level_type:str; price:float; available_at:int; source_start:int

@dataclass
class Level:
    id:int; symbol:str; timeframe:str; level_type:str; price:float; trigger:float; available_at:int; source_start:int
    broken:bool=False; broken_at:Optional[int]=None; in_position:bool=False; armed:bool=True; entries:int=0

@dataclass
class EngineTrade:
    symbol:str; level_id:int; timeframe:str; level_type:str; direction:str; level_price:float; trigger_price:float
    source_start:int; entry_time:int; entry_price:float; quantity:float; take_profit:float; stop_loss:float
    entry_fee:float; entry_was_intrabar:bool; exit_time:Optional[int]=None; exit_price:Optional[float]=None
    exit_reason:Optional[str]=None; exit_fee:float=0.0; gross_pnl:float=0.0; net_pnl:float=0.0; level_broken_at_exit:bool=False

class BacktestEngine:
    """Event-driven port of the original 28-variant level simulator."""

    def __init__(self,symbol:str,config:BacktestConfig):
        self.symbol=symbol; self.config=config
        self.levels:Dict[int,Level]={}; self.open_positions:Dict[int,EngineTrade]={}; self.closed_trades:List[EngineTrade]=[]
        self._next_level_id=1
        self._high_entry_heap=[]; self._low_entry_heap=[]; self._high_break_heap=[]; self._low_break_heap=[]
        self._long_tp_heap=[]; self._long_sl_heap=[]; self._short_sl_heap=[]; self._short_tp_heap=[]
        self.last_candle=None; self._pending_rearm=set()

    def add_level(self,seed:LevelSeed)->int:
        if seed.price<=0: raise ValueError('level price must be positive')
        if seed.level_type not in {'HIGH','LOW'}: raise ValueError('level_type must be HIGH or LOW')
        lid=self._next_level_id; self._next_level_id+=1
        trigger=seed.price*(1-self.config.entry_distance) if seed.level_type=='HIGH' else seed.price*(1+self.config.entry_distance)
        level=Level(lid,self.symbol,seed.timeframe,seed.level_type,seed.price,trigger,seed.available_at,seed.source_start)
        self.levels[lid]=level
        if seed.level_type=='HIGH':
            heapq.heappush(self._high_entry_heap,(trigger,lid)); heapq.heappush(self._high_break_heap,(seed.price,lid))
        else:
            heapq.heappush(self._low_entry_heap,(-trigger,lid)); heapq.heappush(self._low_break_heap,(-seed.price,lid))
        return lid

    def _rearm(self,level):
        if level.broken or level.in_position:return
        if self.config.max_entries_per_level is not None and level.entries>=self.config.max_entries_per_level:
            level.armed=False; return
        level.armed=True
        heapq.heappush(self._high_entry_heap,(level.trigger,level.id)) if level.level_type=='HIGH' else heapq.heappush(self._low_entry_heap,(-level.trigger,level.id))

    def _mark_broken(self,level,ts):
        if not level.broken:
            level.broken=True; level.broken_at=ts; level.armed=False

    def _close_trade(self,trade,ts,price,reason):
        if trade.exit_time is not None:return
        level=self.levels[trade.level_id]
        trade.exit_time=ts; trade.exit_price=price; trade.exit_reason=reason
        trade.exit_fee=trade.quantity*price*self.config.taker_fee
        trade.gross_pnl=trade.quantity*(price-trade.entry_price) if trade.direction=='LONG' else trade.quantity*(trade.entry_price-price)
        trade.net_pnl=trade.gross_pnl-trade.entry_fee-trade.exit_fee
        trade.level_broken_at_exit=level.broken; level.in_position=False
        self.open_positions.pop(level.id,None); self.closed_trades.append(trade)
        if reason=='SL' and not level.broken:self._pending_rearm.add(level.id)

    def _open_trade(self,level,candle,entry_price,intrabar):
        if level.broken or level.in_position or not level.armed:return
        if level.level_type not in self.config.allowed_level_types:
            level.armed=False; return
        if self.config.max_level_age_ms is not None and candle.ts-level.available_at>self.config.max_level_age_ms:
            level.armed=False; return
        if self.config.max_entries_per_level is not None and level.entries>=self.config.max_entries_per_level:
            level.armed=False; return
        direction=self.config.high_direction if level.level_type=='HIGH' else self.config.low_direction
        if direction not in {'LONG','SHORT'}:raise ValueError('invalid direction')
        qty=self.config.position_usd/entry_price
        if direction=='LONG':tp=entry_price*(1+self.config.take_profit); sl=entry_price*(1-self.config.stop_loss)
        else:tp=entry_price*(1-self.config.take_profit); sl=entry_price*(1+self.config.stop_loss)
        trade=EngineTrade(self.symbol,level.id,level.timeframe,level.level_type,direction,level.price,level.trigger,level.source_start,candle.ts,entry_price,qty,tp,sl,self.config.position_usd*self.config.taker_fee,intrabar)
        level.in_position=True; level.armed=False; level.entries+=1; self.open_positions[level.id]=trade
        if direction=='LONG':
            heapq.heappush(self._long_tp_heap,(tp,level.id)); heapq.heappush(self._long_sl_heap,(-sl,level.id))
        else:
            heapq.heappush(self._short_sl_heap,(sl,level.id)); heapq.heappush(self._short_tp_heap,(-tp,level.id))

    def _valid(self,lid,direction=None):
        t=self.open_positions.get(lid)
        return t if t is not None and (direction is None or t.direction==direction) else None

    def _process_existing_exits(self,c):
        for t in list(self.open_positions.values()):
            if t.direction=='LONG':
                if c.open<=t.stop_loss:self._close_trade(t,c.ts,c.open,'SL')
                elif c.open>=t.take_profit:self._close_trade(t,c.ts,t.take_profit,'TP')
            else:
                if c.open>=t.stop_loss:self._close_trade(t,c.ts,c.open,'SL')
                elif c.open<=t.take_profit:self._close_trade(t,c.ts,t.take_profit,'TP')
        while self._long_sl_heap and -self._long_sl_heap[0][0]>=c.low:
            n,lid=heapq.heappop(self._long_sl_heap); t=self._valid(lid,'LONG')
            if t and math.isclose(t.stop_loss,-n,rel_tol=1e-12,abs_tol=1e-12):self._close_trade(t,c.ts,t.stop_loss,'SL')
        while self._short_sl_heap and self._short_sl_heap[0][0]<=c.high:
            p,lid=heapq.heappop(self._short_sl_heap); t=self._valid(lid,'SHORT')
            if t and math.isclose(t.stop_loss,p,rel_tol=1e-12,abs_tol=1e-12):self._close_trade(t,c.ts,t.stop_loss,'SL')
        while self._long_tp_heap and self._long_tp_heap[0][0]<=c.high:
            p,lid=heapq.heappop(self._long_tp_heap); t=self._valid(lid,'LONG')
            if t and math.isclose(t.take_profit,p,rel_tol=1e-12,abs_tol=1e-12):self._close_trade(t,c.ts,t.take_profit,'TP')
        while self._short_tp_heap and -self._short_tp_heap[0][0]>=c.low:
            n,lid=heapq.heappop(self._short_tp_heap); p=-n; t=self._valid(lid,'SHORT')
            if t and math.isclose(t.take_profit,p,rel_tol=1e-12,abs_tol=1e-12):self._close_trade(t,c.ts,t.take_profit,'TP')

    def _break_gaps_at_open(self,c):
        while self._high_break_heap and self._high_break_heap[0][0]<c.open:
            p,lid=heapq.heappop(self._high_break_heap); level=self.levels[lid]
            if not level.broken and math.isclose(level.price,p,rel_tol=1e-12,abs_tol=1e-12):self._mark_broken(level,c.ts)
        while self._low_break_heap and -self._low_break_heap[0][0]>c.open:
            n,lid=heapq.heappop(self._low_break_heap); p=-n; level=self.levels[lid]
            if not level.broken and math.isclose(level.price,p,rel_tol=1e-12,abs_tol=1e-12):self._mark_broken(level,c.ts)

    def _process_new_entries(self,c):
        while self._high_entry_heap and self._high_entry_heap[0][0]<=c.high:
            trigger,lid=heapq.heappop(self._high_entry_heap); level=self.levels[lid]
            if level.broken or level.in_position or not level.armed or not math.isclose(level.trigger,trigger,rel_tol=1e-12,abs_tol=1e-12):continue
            if c.open>level.price:self._mark_broken(level,c.ts); continue
            entry,intrabar=(c.open,False) if c.open>=trigger else (trigger,True)
            self._open_trade(level,c,entry,intrabar)
            if not intrabar:
                t=self.open_positions.get(lid)
                if t:
                    sl_hit=c.low<=t.stop_loss if t.direction=='LONG' else c.high>=t.stop_loss
                    tp_hit=c.high>=t.take_profit if t.direction=='LONG' else c.low<=t.take_profit
                    if sl_hit:self._close_trade(t,c.ts,t.stop_loss,'SL')
                    elif tp_hit:self._close_trade(t,c.ts,t.take_profit,'TP')
        while self._low_entry_heap and -self._low_entry_heap[0][0]>=c.low:
            n,lid=heapq.heappop(self._low_entry_heap); trigger=-n; level=self.levels[lid]
            if level.broken or level.in_position or not level.armed or not math.isclose(level.trigger,trigger,rel_tol=1e-12,abs_tol=1e-12):continue
            if c.open<level.price:self._mark_broken(level,c.ts); continue
            entry,intrabar=(c.open,False) if c.open<=trigger else (trigger,True)
            self._open_trade(level,c,entry,intrabar)
            if not intrabar:
                t=self.open_positions.get(lid)
                if t:
                    sl_hit=c.low<=t.stop_loss if t.direction=='LONG' else c.high>=t.stop_loss
                    tp_hit=c.high>=t.take_profit if t.direction=='LONG' else c.low<=t.take_profit
                    if sl_hit:self._close_trade(t,c.ts,t.stop_loss,'SL')
                    elif tp_hit:self._close_trade(t,c.ts,t.take_profit,'TP')

    def _break_intraminute(self,c):
        while self._high_break_heap and self._high_break_heap[0][0]<c.high:
            p,lid=heapq.heappop(self._high_break_heap); level=self.levels[lid]
            if not level.broken and math.isclose(level.price,p,rel_tol=1e-12,abs_tol=1e-12):self._mark_broken(level,c.ts)
        while self._low_break_heap and -self._low_break_heap[0][0]>c.low:
            n,lid=heapq.heappop(self._low_break_heap); p=-n; level=self.levels[lid]
            if not level.broken and math.isclose(level.price,p,rel_tol=1e-12,abs_tol=1e-12):self._mark_broken(level,c.ts)

    def process_minute(self,c):
        self._break_gaps_at_open(c); self._process_existing_exits(c); self._process_new_entries(c); self._break_intraminute(c)
        if self._pending_rearm:
            pending=list(self._pending_rearm); self._pending_rearm.clear()
            for lid in pending:
                level=self.levels[lid]
                if not level.broken and not level.in_position:self._rearm(level)
        self.last_candle=c

    def close_end_of_data(self):
        if self.last_candle is None:return
        for t in list(self.open_positions.values()):self._close_trade(t,self.last_candle.ts,self.last_candle.close,'END_OF_DATA')


from datetime import datetime, timezone

@dataclass
class _AggBar:
    key:tuple
    start_ts:int
    open:float
    high:float
    low:float
    close:float

class MultiTimeframeAggregator:
    TIMEFRAMES=('1H','1D','1M','1Y')
    @staticmethod
    def _dt(ts):
        return datetime.fromtimestamp(ts/1000.0,tz=timezone.utc)
    @classmethod
    def _key(cls,timeframe,ts):
        d=cls._dt(ts)
        if timeframe=='1H': return (d.year,d.month,d.day,d.hour)
        if timeframe=='1D': return (d.year,d.month,d.day)
        if timeframe=='1M': return (d.year,d.month)
        if timeframe=='1Y': return (d.year,)
        raise ValueError(timeframe)
    def __init__(self): self._bars={}
    def push(self,candle):
        created=[]
        for tf in self.TIMEFRAMES:
            key=self._key(tf,candle.ts); bar=self._bars.get(tf)
            if bar is None:
                self._bars[tf]=_AggBar(key,candle.ts,candle.open,candle.high,candle.low,candle.close); continue
            if key!=bar.key:
                created.append(LevelSeed(tf,'HIGH',bar.high,candle.ts,bar.start_ts))
                created.append(LevelSeed(tf,'LOW',bar.low,candle.ts,bar.start_ts))
                self._bars[tf]=_AggBar(key,candle.ts,candle.open,candle.high,candle.low,candle.close)
            else:
                bar.high=max(bar.high,candle.high); bar.low=min(bar.low,candle.low); bar.close=candle.close
        return created

def _trade_row(t):
    return {
        'symbol':t.symbol,'level_id':t.level_id,'timeframe':t.timeframe,'level_type':t.level_type,
        'direction':t.direction,'entry_time':t.entry_time,'entry_price':t.entry_price,
        'take_profit':t.take_profit,'stop_loss':t.stop_loss,'exit_time':t.exit_time,
        'exit_price':t.exit_price,'exit_reason':t.exit_reason,'gross_pnl':t.gross_pnl,
        'net_pnl':t.net_pnl,'fees':t.entry_fee+t.exit_fee,
    }

def run_legacy_suite(candles,variant_names=None):
    rows=list(candles)
    variants=legacy_variants()
    names=tuple(variant_names) if variant_names is not None else tuple(variants)
    unknown=set(names)-set(variants)
    if unknown: raise KeyError(f'unknown variants: {sorted(unknown)}')
    engines={name:BacktestEngine('HISTORY',variants[name]) for name in names}
    agg=MultiTimeframeAggregator()
    for candle in rows:
        for seed in agg.push(candle):
            for engine in engines.values():
                if seed.level_type in engine.config.allowed_level_types:
                    engine.add_level(seed)
        for engine in engines.values():
            engine.process_minute(candle)
    out={}
    for name,engine in engines.items():
        engine.close_end_of_data()
        out[name]={
            'candles_processed':len(rows),
            'trades':[_trade_row(t) for t in engine.closed_trades],
            'levels':[{'id':x.id,'timeframe':x.timeframe,'level_type':x.level_type,'price':x.price,'available_at':x.available_at,'source_start':x.source_start,'broken':x.broken,'entries':x.entries} for x in engine.levels.values()],
        }
    return out


class LegacyGridStrategy:
    id='legacy_grid'
    version='1.0'
    requirements=(DataRequirement('candles',('1m',)),)
    def run(self,candles,checkpoint=None):
        rows=[MinuteCandle(c.open_time,c.open,c.high,c.low,c.close,c.volume,c.turnover or 0.0) if hasattr(c,'open_time') else c for c in candles]
        return {'variants':run_legacy_suite(rows),'candles_processed':len(rows),'checkpoint':checkpoint}
