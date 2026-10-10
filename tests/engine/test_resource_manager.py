from strattester.engine.resource_manager import *
GB=1024**3

def snap(used,cpu=8,cpu_percent=0):
    return ResourceSnapshot(100*GB,int((100-used)*GB),100*GB,cpu_percent,cpu)

def test_ram_thresholds():
    assert decide_resources(snap(70)).action=='normal'
    assert decide_resources(snap(80)).action=='throttle'
    assert decide_resources(snap(88)).action=='pause'
    assert decide_resources(snap(95)).action=='checkpoint_release'

def test_low_absolute_disk_blocks():
    assert decide_resources(ResourceSnapshot(32*GB,16*GB,1*GB,0,8)).allow_heavy is False

def test_slots_scale_with_cpu_and_leave_headroom():
    d=decide_resources(ResourceSnapshot(64*GB,48*GB,100*GB,20,8))
    assert d.action=='normal'
    assert d.max_new_jobs==7

def test_cpu_pressure_reduces_or_pauses_work():
    assert decide_resources(ResourceSnapshot(64*GB,48*GB,100*GB,85,8)).action=='cpu_throttle'
    assert decide_resources(ResourceSnapshot(64*GB,48*GB,100*GB,98,8)).allow_heavy is False

def test_ram_can_limit_cpu_parallelism():
    d=decide_resources(ResourceSnapshot(8*GB,5*GB,100*GB,20,16))
    assert d.max_new_jobs==1


def test_heavy_jobs_pause_when_reserved_ram_would_be_consumed():
    decision=decide_resources(ResourceSnapshot(8*GB,3*GB,100*GB,0,16))
    assert decision.allow_heavy is False
    assert decision.max_new_jobs==0
    assert decision.action=='pause'


def test_ram_reserve_applies_to_custom_minimum_and_job_slots():
    snap=ResourceSnapshot(8*GB,4*GB,100*GB,0,16)
    assert decide_resources(snap).max_new_jobs==1
    assert decide_resources(snap,min_free_ram=3*GB).max_new_jobs==0
    assert decide_resources(snap,min_free_ram=3*GB).allow_heavy is False
