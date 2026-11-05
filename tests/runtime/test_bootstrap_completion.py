from dataclasses import replace
from pathlib import Path
from strattester.engine.jobs import Job,JobState
from strattester.runtime.bootstrap_completion import BootstrapCompletionCoordinator
from strattester.persistence.data_first_store import DataFirstStateStore
from tests.engine.test_data_first_scheduler import setup
import pytest

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


@pytest.mark.parametrize('state',[JobState.CANCELLED,JobState.BLOCKED,JobState.PENDING])
def test_only_successful_completion_is_terminal_for_handoff(tmp_path,state):
    c=BootstrapCompletionCoordinator(State([Job.new('x').with_state(state)]),Market(),tmp_path)
    assert not c.status()['ready_to_finalize']


def completed_data_first(tmp_path):
    scheduler,state,_,_,stores=setup(tmp_path)
    scheduler.discover();scheduler.plan(start_ms=0,end_ms=180000)
    for _ in range(4):scheduler.tick()
    assert state.jobs()[0]['state']=='COMPLETED'
    return scheduler,state,stores


def test_real_data_first_jobs_adapt_without_invented_legacy_jobs(tmp_path):
    _,state,stores=completed_data_first(tmp_path)
    market=stores('linear')
    try:
        coordinator=BootstrapCompletionCoordinator(state,market,tmp_path/'completion')
        assert coordinator.status()['ready_to_finalize']
        result=coordinator.finalize_if_ready(['ALPHAUSDT'])
        assert result['finalized'] is False
        assert result['ready_to_finalize'] is False
        assert result['reason']=='SCIENTIFIC_DATA_INCOMPLETE'
        assert not (tmp_path/'completion/results/grid-handoff.json').exists()
        assert coordinator.phase.load()['phase']!='GRID_IMPORT'
    finally:market.close()


def test_missing_requested_symbol_and_changed_completed_inputs_block(tmp_path):
    _,state,stores=completed_data_first(tmp_path)
    market=stores('linear')
    try:
        coordinator=BootstrapCompletionCoordinator(state,market,tmp_path/'completion')
        assert coordinator.finalize_if_ready(['ALPHAUSDT','MISSINGUSDT'])['reason']=='REQUESTED_JOBS_MISSING'
        market.connection.execute('UPDATE candles SET volume=volume+1')
        market.connection.commit()
        assert coordinator.finalize_if_ready(['ALPHAUSDT'])['reason']=='COMPLETED_INPUTS_CHANGED'
    finally:market.close()


def test_empty_real_job_store_never_finalizes(tmp_path):
    coordinator=BootstrapCompletionCoordinator(DataFirstStateStore(tmp_path/'jobs.db'),Market(),tmp_path/'completion')
    assert coordinator.finalize_if_ready(['BTCUSDT'])['finalized'] is False


def test_scheduler_wires_real_completion_and_closes_category_store(tmp_path):
    scheduler,_,_=completed_data_first(tmp_path)
    report=scheduler.finalize_bootstrap(tmp_path/'completion')
    assert report['linear']['finalized'] is False
    assert report['linear']['reason']=='SCIENTIFIC_DATA_INCOMPLETE'


def test_completed_job_without_result_cannot_be_ignored(tmp_path):
    _,state,stores=completed_data_first(tmp_path)
    with state.connection() as connection:
        connection.execute('UPDATE df_jobs SET result=NULL')
    market=stores('linear')
    try:
        result=BootstrapCompletionCoordinator(state,market,tmp_path/'completion').finalize_if_ready(['ALPHAUSDT'])
        assert result['finalized'] is False
    finally:market.close()


def test_changed_instrument_metadata_invalidates_completed_job(tmp_path):
    _,state,stores=completed_data_first(tmp_path)
    state.snapshot('linear',[{'symbol':'ALPHAUSDT','status':'Suspended','launchTime':'0'}],600001)
    market=stores('linear')
    try:
        result=BootstrapCompletionCoordinator(state,market,tmp_path/'completion').finalize_if_ready(['ALPHAUSDT'])
        assert result['reason']=='COMPLETED_INSTRUMENT_CHANGED'
    finally:market.close()
