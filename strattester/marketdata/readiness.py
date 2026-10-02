from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from strattester.bootstrap import bootstrap
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine

@dataclass(frozen=True)
class OpenedMarketStore:
    path:Path
    store:SQLiteMarketStore
    source_mode:str

def open_market_store(root:Path,legacy_paths=()):
    b=bootstrap(root,legacy_paths=legacy_paths)
    path=b.market_db or b.config.market_db
    store=SQLiteMarketStore.open(path)
    mode=b.mode if b.market_db is not None else 'created'
    return OpenedMarketStore(Path(path),store,mode)

def ensure_history(store,client,requirements,clock_ms=None):
    engine=SyncEngine(store,client,clock_ms=clock_ms)
    return tuple(engine.sync_requirement(req) for req in requirements)


def requirements_for_instrument(instrument:dict,*,end_ms:int):
    from strattester.marketdata.sync_engine import DataRequirement
    symbol=instrument['symbol']
    launch=int(instrument.get('launchTime') or 0)
    launch=(launch//60_000)*60_000
    funding_minutes=int(instrument.get('fundingInterval') or 480)
    return (
        DataRequirement(symbol,'candles','1m',launch,end_ms),
        DataRequirement(symbol,'mark_price','1m',launch,end_ms),
        DataRequirement(symbol,'index_price','1m',launch,end_ms),
        DataRequirement(symbol,'premium_index','1m',launch,end_ms),
        DataRequirement(symbol,'open_interest','5m',launch,end_ms),
        DataRequirement(symbol,'funding',f'{funding_minutes}m',launch,end_ms),
        DataRequirement(symbol,'long_short_ratio','5m',launch,end_ms),
    )

def ensure_instrument_history(store,client,instrument,*,end_ms:int,clock_ms=None):
    return ensure_history(store,client,requirements_for_instrument(instrument,end_ms=end_ms),clock_ms=clock_ms)
