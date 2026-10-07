from .jobs import JobState
from .resource_manager import decide_resources

class Scheduler:
    def __init__(self,state_store,max_sync_jobs_per_node=4):
        self.state_store=state_store
        self.max_sync_jobs_per_node=max(1,int(max_sync_jobs_per_node))
    def recover_stale_jobs(self,now):
        out=[]
        for j in self.state_store.list_jobs():
            r=j.recover_stale(now)
            if r!=j: self.state_store.put_job(r)
            out.append(r)
        return out
    def ready_jobs(self,snapshot,node_id=None):
        d=decide_resources(snapshot)
        if not d.allow_heavy: return []
        jobs=[j for j in self.state_store.list_jobs()
              if j.state in (JobState.READY,JobState.RETRYABLE)]
        if node_id is not None:
            jobs=[j for j in jobs if j.target_node in (None,node_id)]
        sync=[j for j in jobs if j.job_type=='sync'][:min(self.max_sync_jobs_per_node,d.max_new_jobs)]
        remaining=max(0,d.max_new_jobs-len(sync))
        other=[j for j in jobs if j.job_type!='sync'][:remaining]
        return sync+other
