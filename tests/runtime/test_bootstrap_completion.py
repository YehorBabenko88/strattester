from dataclasses import replace
from pathlib import Path
from strattester.engine.jobs import Job,JobState
from strattester.runtime.bootstrap_completion import BootstrapCompletionCoordinator

class State:
    def __init__(self,jobs):self.jobs=jobs
    def list_jobs(self):return self.jobs

class Market: pass

def test_completion_waits_for_all_terminal_jobs(tmp_path):
    c=BootstrapCompletionCoordinator(State([Job.new("x").with_state(JobState.RUNNING)]),Market(),tmp_path)
    s=c.status()
    assert not s["ready_to_finalize"] and s["active"]==1

def test_failed_job_blocks_handoff(tmp_path):
    c=BootstrapCompletionCoordinator(State([Job.new("x").with_state(JobState.FAILED)]),Market(),tmp_path)
    assert not c.status()["ready_to_finalize"]
