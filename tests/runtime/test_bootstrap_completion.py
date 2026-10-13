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


def test_finalized_handoff_remains_valid_after_phase_advance(monkeypatch, tmp_path):
    from strattester.runtime import bootstrap_completion
    from strattester.runtime.grid_handoff import verify_handoff
    from strattester.runtime.phase_manifest import PhaseManifest

    def export_stub(market, symbols, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"symbols":["BTCUSDT"]}', encoding="utf-8")
        return {"symbols": ["BTCUSDT"]}

    monkeypatch.setattr(bootstrap_completion, "export_scientific_bootstrap", export_stub)
    completed = Job.new("x").with_state(JobState.COMPLETE)
    coordinator = BootstrapCompletionCoordinator(State([completed]), Market(), tmp_path)
    result = coordinator.finalize_if_ready(["BTCUSDT"])
    assert result["finalized"] is True
    assert PhaseManifest(tmp_path / "state" / "phase-manifest.json").load()["phase"] == "GRID_IMPORT"
    assert verify_handoff(result["handoff"])["phase_manifest"] is None


def test_phase_manifest_advance_records_completed_phase_names(tmp_path):
    from strattester.runtime.phase_manifest import PhaseManifest, PHASES

    manifest = PhaseManifest(tmp_path / "state" / "phase-manifest.json")
    advanced = manifest.advance("GRID_IMPORT")
    assert advanced["phase"] == "GRID_IMPORT"
    assert advanced["completed"] == list(PHASES[:PHASES.index("GRID_IMPORT")])
    assert manifest.load()["completed"] == advanced["completed"]


def test_cancelled_jobs_cannot_finalize_bootstrap(tmp_path):
    cancelled = Job.new("x").with_state(JobState.CANCELLED)
    coordinator = BootstrapCompletionCoordinator(State([cancelled]), Market(), tmp_path)
    status = coordinator.status()
    assert status["cancelled"] == 1
    assert status["complete"] == 0
    assert status["ready_to_finalize"] is False
    assert coordinator.finalize_if_ready(["BTCUSDT"])["finalized"] is False


def test_mixed_completed_and_cancelled_jobs_cannot_finalize(tmp_path):
    jobs = [Job.new("x").with_state(JobState.COMPLETE),
            Job.new("y").with_state(JobState.CANCELLED)]
    status = BootstrapCompletionCoordinator(State(jobs), Market(), tmp_path).status()
    assert status["complete"] == 1
    assert status["cancelled"] == 1
    assert status["ready_to_finalize"] is False
