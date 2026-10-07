from __future__ import annotations
from pathlib import Path
from .sqlite_store import SQLiteMarketStore
from .sharded_store import ShardedMarketStore

def open_market_store(market_db:Path,shards_dir:Path|None=None):
    """Open the authoritative routed market backend.

    Existing installations keep their monolithic database as the authoritative
    source until each symbol is individually promoted in the shard manifest.
    New installations without a legacy DB can write directly to shards.
    """
    market_db=Path(market_db)
    if shards_dir is None:
        return SQLiteMarketStore.open(market_db)
    legacy=SQLiteMarketStore.open(market_db) if market_db.exists() else None
    return ShardedMarketStore(Path(shards_dir),legacy_store=legacy)


def open_configured_market_store(config):
    """Canonical production entry point for sync/research market storage."""
    return open_market_store(config.market_db,getattr(config,'market_shards_dir',None))
