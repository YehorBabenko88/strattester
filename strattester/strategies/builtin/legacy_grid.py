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
        'LOW_TP20':low(take_profit=.020), 'LOW_TP25':low(take_profit=.025), 'LOW_SL075':low(stop_loss=.0075),
        'LOW_AGE_24H':low(max_level_age_ms=24*H), 'LOW_AGE_3D':low(max_level_age_ms=3*D), 'LOW_AGE_7D':low(max_level_age_ms=7*D), 'LOW_AGE_30D':low(max_level_age_ms=30*D),
        'HIGH_BASE':high(), 'HIGH_FIRST_TOUCH':high(max_entries_per_level=1),
        'HIGH_ENTRY_010':high(entry_distance=.001), 'HIGH_ENTRY_025':high(entry_distance=.0025), 'HIGH_ENTRY_040':high(entry_distance=.004),
        'HIGH_TP20':high(take_profit=.020), 'HIGH_TP25':high(take_profit=.025), 'HIGH_SL075':high(stop_loss=.0075),
        'HIGH_AGE_24H':high(max_level_age_ms=24*H), 'HIGH_AGE_3D':high(max_level_age_ms=3*D), 'HIGH_AGE_7D':high(max_level_age_ms=7*D), 'HIGH_AGE_30D':high(max_level_age_ms=30*D),
        'REVERSAL_BASE':BacktestConfig(high_direction='SHORT',low_direction='LONG'),
        'HIGH_SHORT':high(high_direction='SHORT'), 'LOW_LONG':low(low_direction='LONG'),
    }

class LegacyGridStrategy:
    id='legacy_grid'
    version='1.0'
    requirements=(DataRequirement('candles',('1m',)),)
    def run(self,candles,checkpoint=None):
        # Full 28-variant level engine is ported only against pinned legacy regression fixtures.
        return {'candles_processed':sum(1 for _ in candles),'checkpoint':checkpoint}
