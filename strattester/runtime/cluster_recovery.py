from __future__ import annotations
import time
from dataclasses import dataclass
from strattester.engine.distribution import reassign_unavailable
from strattester.engine.jobs import JobState

@dataclass(frozen=True)
class RecoveryReport:
    live_nodes: tuple[str,...]
    reassigned: tuple[str,...]
    deferred: tuple[str,...]

class ClusterRecovery:
    def __init__(self,state_store,node_stale_after=30):
        self.state_store=state_store
        self.node_stale_after=float(node_stale_after)

    def reconcile(self,now=None):
        now=time.time() if now is None else float(now)
        if not hasattr(self.state_store,'live_nodes'):
            return RecoveryReport((),(),())
        live=tuple(self.state_store.live_nodes(self.node_stale_after,now))
        if not live:
            return RecoveryReport((),(),())
        reassigned=[]; deferred=[]
        for job in self.state_store.list_jobs():
            if job.target_node is None or job.target_node in live:
                continue
            if job.state in (JobState.COMPLETE,JobState.CANCELLED,JobState.FAILED):
                continue
            if job.state in (JobState.LEASED,JobState.RUNNING) and job.lease_until is not None and job.lease_until>=now:
                deferred.append(job.id)
                continue
            moved=reassign_unavailable(job.recover_stale(now),live)
            if hasattr(self.state_store,'compare_and_swap_job'):
                if self.state_store.compare_and_swap_job(job,moved):
                    reassigned.append(job.id)
                else:
                    deferred.append(job.id)
            else:
                self.state_store.put_job(moved)
                reassigned.append(job.id)
        return RecoveryReport(live,tuple(reassigned),tuple(deferred))
