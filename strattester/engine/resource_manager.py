from dataclasses import dataclass
import os
import math

GB=1024**3

@dataclass(frozen=True)
class ResourceSnapshot:
    total_ram:int
    available_ram:int
    disk_free:int
    cpu_percent:float=0.0
    cpu_count:int=0
    @property
    def ram_used_ratio(self): return 1-(self.available_ram/max(1,self.total_ram))
    @property
    def effective_cpu_count(self): return max(1,self.cpu_count or (os.cpu_count() or 1))

@dataclass(frozen=True)
class SchedulingDecision:
    allow_heavy:bool
    max_new_jobs:int
    action:str

def _normal_slots(s:ResourceSnapshot,ram_per_job:int=2*GB,max_jobs:int=16):
    cpu_slots=max(1,s.effective_cpu_count-1)
    ram_slots=max(1,s.available_ram//max(1,ram_per_job))
    return int(max(1,min(cpu_slots,ram_slots,max_jobs)))

def _finite_nonnegative(value):
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except (TypeError, ValueError, OverflowError):
        return False


def decide_resources(s:ResourceSnapshot,min_free_ram=2*GB,min_free_disk=5*GB):
    # Missing or inconsistent resource telemetry must not authorize heavy jobs.
    if (not all(_finite_nonnegative(value) for value in
                (s.total_ram, s.available_ram, s.disk_free))
            or s.total_ram == 0 or s.available_ram > s.total_ram):
        return SchedulingDecision(False,0,'checkpoint_release')
    if (not _finite_nonnegative(s.cpu_percent) or s.cpu_percent > 100
            or not isinstance(s.cpu_count, int) or isinstance(s.cpu_count, bool)
            or s.cpu_count < 0):
        return SchedulingDecision(False,0,'pause')
    if s.available_ram<min_free_ram or s.disk_free<min_free_disk or s.ram_used_ratio>0.92:
        return SchedulingDecision(False,0,'checkpoint_release')
    if s.ram_used_ratio>=0.85 or s.cpu_percent>=97:
        return SchedulingDecision(False,0,'pause')
    if s.ram_used_ratio>=0.75 or s.cpu_percent>=90:
        return SchedulingDecision(True,1,'throttle')
    slots=_normal_slots(s)
    if s.cpu_percent>=80:
        slots=max(1,slots//2)
        return SchedulingDecision(True,slots,'cpu_throttle')
    return SchedulingDecision(True,slots,'normal')
