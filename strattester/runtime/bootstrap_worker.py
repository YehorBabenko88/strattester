from __future__ import annotations
from pathlib import Path
from strattester.bootstrap import bootstrap
from strattester.engine.scheduler import Scheduler
from strattester.persistence.sqlite_state_store import SQLiteStateStore
from strattester.runtime.lifecycle import Lifecycle
from strattester.runtime.logging import build_logger
from strattester.runtime.system_resources import snapshot
from strattester.runtime.worker import WorkerRuntime

def build_worker(root:Path,executor):
    b=bootstrap(root)
    state=SQLiteStateStore.open(b.state_db)
    logger=build_logger(b.config.logs_dir/'worker.jsonl','strattester.worker')
    runtime=WorkerRuntime(state,Scheduler(state),executor,Lifecycle(),logger,lambda:snapshot(b.config.root))
    return b,state,runtime
