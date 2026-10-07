from __future__ import annotations
from pathlib import Path
from strattester.bootstrap import bootstrap
from strattester.engine.scheduler import Scheduler
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.persistence.postgres_state_store import PostgresStateStore
from strattester.runtime.lifecycle import Lifecycle
from strattester.runtime.logging import build_logger
from strattester.runtime.system_resources import snapshot
from strattester.runtime.worker import WorkerRuntime
from strattester.runtime.background_migration import BackgroundShardMigration
from strattester.marketdata.store_factory import open_market_store
from strattester.marketdata.sharded_store import ShardedMarketStore
from strattester.marketdata.shard_migrator import ShardMigrator
from strattester.engine.distribution import assign_node

def build_worker(root:Path,executor):
    b=bootstrap(root)
    state=(PostgresStateStore.connect(b.config.postgres_dsn)
           if b.config.postgres_dsn else SQLiteStateStore.open(b.state_db))
    logger=build_logger(b.config.logs_dir/'worker.jsonl','strattester.worker')
    background=[]
    if b.config.market_db.exists() and b.config.market_shards_dir is not None:
        shards=open_market_store(b.config.market_db,b.config.market_shards_dir)
        legacy=shards.legacy_store
        def assigned_symbols():
            connection=getattr(legacy,'connection',None)
            symbols=connection.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol").fetchall()
            names=[r[0] for r in symbols]
            if not b.config.node_id or not hasattr(state,'live_nodes'):
                return names
            try: nodes=state.live_nodes()
            except Exception: return ()
            return [s for s in names if nodes and assign_node(s,nodes)==b.config.node_id]
        background.append(BackgroundShardMigration(
            ShardMigrator(shards),assigned_symbols,lambda:snapshot(b.config.root),
            b.config.min_free_disk_bytes,batch_symbols=2,interval_seconds=60))
    runtime=WorkerRuntime(
        state,Scheduler(state),executor,Lifecycle(),logger,
        lambda:snapshot(b.config.root),
        node_id=b.config.node_id,
        execution_mode=b.config.execution_mode,
        background_tasks=background,
        resources=([shards,legacy] if background and legacy is not None else ([shards] if background else [])))
    return b,state,runtime
