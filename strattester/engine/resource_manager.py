from dataclasses import dataclass
import os

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

def _normal_slots(s:ResourceSnapshot,ram_per_job:int=2*GB,max_jobs:int=16,reserve_ram:int=2*GB):
    cpu_slots=max(1,s.effective_cpu_count-1)
    # New jobs must not consume the RAM reserved for the OS and services.
    ram_slots=max(0,(s.available_ram-max(0,reserve_ram))//max(1,ram_per_job))
    return int(max(0,min(cpu_slots,ram_slots,max_jobs)))

def decide_resources(s:ResourceSnapshot,min_free_ram=2*GB,min_free_disk=5*GB):
    if s.available_ram<min_free_ram or s.disk_free<min_free_disk or s.ram_used_ratio>0.92:
        return SchedulingDecision(False,0,'checkpoint_release')
    slots=_normal_slots(s,reserve_ram=min_free_ram)
    if slots<1:
        return SchedulingDecision(False,0,'pause')
    if s.ram_used_ratio>=0.85 or s.cpu_percent>=97:
        return SchedulingDecision(False,0,'pause')
    if s.ram_used_ratio>=0.75 or s.cpu_percent>=90:
        return SchedulingDecision(True,1,'throttle')
    if s.cpu_percent>=80:
        slots=max(1,slots//2)
        return SchedulingDecision(True,slots,'cpu_throttle')
    return SchedulingDecision(True,slots,'normal')
