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
