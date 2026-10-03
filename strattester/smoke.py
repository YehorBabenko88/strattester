from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging
from .engine.jobs import Job,JobState
from .engine.scheduler import Scheduler
from .engine.resource_manager import ResourceSnapshot
from .persistence.sqlite_state_store import SQLiteStateStore
from .runtime.lifecycle import Lifecycle
from .runtime.worker import WorkerRuntime

GB=1024**3
@dataclass(frozen=True)
class SmokeResult:
    ok:bool; job_id:str; state:str; reopened_state:str

def run_worker_smoke(root:Path,fail:bool=False)->SmokeResult:
    root=Path(root); db=root/'state'/'smoke_state.sqlite3'
    store=SQLiteStateStore.open(db)
    job=Job.new('SMOKE',symbol='SMOKE',resource_key='smoke',state=JobState.READY)
    store.put_job(job)
    def execute(_):
        if fail: raise RuntimeError('intentional smoke failure')
    runtime=WorkerRuntime(store,Scheduler(store),execute,Lifecycle(),logging.getLogger('strattester.smoke'),
        lambda:ResourceSnapshot(16*GB,8*GB,20*GB,0))
    runtime.run_once()
    state=store.get_job(job.id).state.value; store.close()
    reopened=SQLiteStateStore.open(db); reopened_state=reopened.get_job(job.id).state.value; reopened.close()
    return SmokeResult(state=='COMPLETE',job.id,state,reopened_state)
