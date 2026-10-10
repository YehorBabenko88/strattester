from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from strattester.bootstrap import bootstrap
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import SyncEngine
from strattester.marketdata.timeframes import aligned_window

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


def dataset_capabilities(instrument:dict):
    """Explicit per-instrument datasets. Unknown metadata stays conservative."""
    caps={"candles","mark_price","index_price","premium_index"}
    if instrument.get("supportsOpenInterest",True):caps.add("open_interest")
    if instrument.get("supportsFunding",instrument.get("fundingInterval") is not None):caps.add("funding")
    if instrument.get("supportsLongShortRatio",True):caps.add("long_short_ratio")
    return frozenset(caps)

def requirements_for_instrument(instrument:dict,*,end_ms:int):
    """Build only physically meaningful history windows for the instrument."""

    from strattester.marketdata.sync_engine import DataRequirement
    symbol=instrument['symbol']
    launch=int(instrument.get('launchTime') or 0)
    end_ms=int(end_ms)
    delist=instrument.get('deliveryTime') or instrument.get('delistTime')
    if delist not in (None,'',0,'0'):
        end_ms=min(end_ms,int(delist))
    if end_ms<launch:return ()
    funding_minutes=int(instrument.get('fundingInterval') or 480)
    caps=dataset_capabilities(instrument)
    specs=(('candles','1m'),('mark_price','1m'),('index_price','1m'),('premium_index','1m'),
           ('open_interest','5m'),('funding',f'{funding_minutes}m'),('long_short_ratio','5m'))
    requirements=[]
    for dataset,timeframe in specs:
        if dataset not in caps:
            continue

        window=aligned_window(
            launch,
            end_ms,
            timeframe,
        )

        if window is None:
            continue

        start,end=window

        requirements.append(
            DataRequirement(
                symbol,
                dataset,
                timeframe,
                start,
                end,
            )
        )
    return tuple(requirements)

def ensure_instrument_history(store,client,instrument,*,end_ms:int,clock_ms=None):
    return ensure_history(store,client,requirements_for_instrument(instrument,end_ms=end_ms),clock_ms=clock_ms)
