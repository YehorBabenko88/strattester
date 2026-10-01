from strattester.engine.resource_manager import *
GB=1024**3
def snap(used): return ResourceSnapshot(100*GB,int((100-used)*GB),100*GB)
def test_ram_thresholds():
    assert decide_resources(snap(70)).action=='normal'
    assert decide_resources(snap(80)).action=='throttle'
    assert decide_resources(snap(88)).action=='pause'
    assert decide_resources(snap(95)).action=='checkpoint_release'
def test_low_absolute_disk_blocks():
    assert decide_resources(ResourceSnapshot(32*GB,16*GB,1*GB)).allow_heavy is False
def test_snapshot_values_are_bytes_not_percent_units():
    s=ResourceSnapshot(100*GB,30*GB,10*GB)
    d=decide_resources(s)
    assert round(s.ram_used_ratio,2)==0.70
    assert d.action=='normal' and d.max_new_jobs==4
