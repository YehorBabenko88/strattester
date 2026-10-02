from .jobs import JobState
from .resource_manager import decide_resources
class Scheduler:
    def __init__(self,state_store): self.state_store=state_store
    def recover_stale_jobs(self,now):
        out=[]
        for j in self.state_store.list_jobs():
            r=j.recover_stale(now)
            if r!=j: self.state_store.put_job(r)
            out.append(r)
        return out
    def ready_jobs(self,snapshot):
        d=decide_resources(snapshot)
        if not d.allow_heavy: return []
        return [j for j in self.state_store.list_jobs() if j.state in (JobState.READY,JobState.RETRYABLE)][:d.max_new_jobs]
