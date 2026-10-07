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

def build_worker(root:Path,executor):
    b=bootstrap(root)
    state=(PostgresStateStore.connect(b.config.postgres_dsn)
           if b.config.postgres_dsn else SQLiteStateStore.open(b.state_db))
    logger=build_logger(b.config.logs_dir/'worker.jsonl','strattester.worker')
    runtime=WorkerRuntime(
        state,Scheduler(state),executor,Lifecycle(),logger,
        lambda:snapshot(b.config.root),
        node_id=b.config.node_id,
        execution_mode=b.config.execution_mode)
    return b,state,runtime
