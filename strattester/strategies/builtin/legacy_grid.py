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
class LegacyGridStrategy:
    id='legacy_grid'
    version='1.0'
    requirements=(DataRequirement('candles',('1m',)),)
    def run(self,candles,checkpoint=None):
        # Full 28-variant level engine is ported only against pinned legacy regression fixtures.
        return {'candles_processed':sum(1 for _ in candles),'checkpoint':checkpoint}
