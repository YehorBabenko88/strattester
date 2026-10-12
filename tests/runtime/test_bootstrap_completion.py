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


def test_export_failure_does_not_advance_phase(monkeypatch, tmp_path):
    import pytest
    from strattester.runtime import bootstrap_completion
    from strattester.runtime.phase_manifest import PhaseManifest

    def fail_export(*args, **kwargs):
        raise RuntimeError("export interrupted")

    monkeypatch.setattr(bootstrap_completion, "export_scientific_bootstrap", fail_export)
    completed = Job.new("x").with_state(JobState.COMPLETE)
    coordinator = BootstrapCompletionCoordinator(State([completed]), Market(), tmp_path)
    with pytest.raises(RuntimeError, match="export interrupted"):
        coordinator.finalize_if_ready(["BTCUSDT"])
    assert PhaseManifest(tmp_path / "state" / "phase-manifest.json").load()["phase"] == "INFRASTRUCTURE"
