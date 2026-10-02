from dataclasses import dataclass
@dataclass(frozen=True)
class ResourceSnapshot:
    total_ram:int
    available_ram:int
    disk_free:int
    cpu_percent:float=0.0
    @property
    def ram_used_ratio(self): return 1-(self.available_ram/max(1,self.total_ram))
@dataclass(frozen=True)
class SchedulingDecision:
    allow_heavy:bool
    max_new_jobs:int
    action:str
def decide_resources(s:ResourceSnapshot,min_free_ram=2*1024**3,min_free_disk=5*1024**3):
    if s.available_ram<min_free_ram or s.disk_free<min_free_disk or s.ram_used_ratio>0.92:
        return SchedulingDecision(False,0,'checkpoint_release')
    if s.ram_used_ratio>=0.85: return SchedulingDecision(False,0,'pause')
    if s.ram_used_ratio>=0.75: return SchedulingDecision(True,1,'throttle')
    return SchedulingDecision(True,4,'normal')
