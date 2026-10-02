from __future__ import annotations
import time,uuid
from strattester.engine.jobs import JobState
class WorkerRuntime:
    def __init__(self,state_store,scheduler,executor,lifecycle,logger,snapshot_provider,worker_id=None,lease_seconds=300):
        self.state_store=state_store; self.scheduler=scheduler; self.executor=executor; self.lifecycle=lifecycle; self.logger=logger; self.snapshot_provider=snapshot_provider
        self.worker_id=worker_id or f'worker-{uuid.uuid4()}'; self.lease_seconds=lease_seconds
    def run_once(self):
        if self.lifecycle.draining or self.lifecycle.stopping:return 0
        candidates=self.scheduler.ready_jobs(self.snapshot_provider())
        if not candidates:return 0
        jobs=self.state_store.claim_ready_jobs(self.worker_id,limit=len(candidates),lease_seconds=self.lease_seconds,job_ids=[j.id for j in candidates])
        for job in jobs:
            running=job.with_state(JobState.RUNNING,attempts=job.attempts+1,lease_owner=self.worker_id)
            self.state_store.put_job(running)
            try:
                self.executor(running)
            except Exception as exc:
                self.state_store.put_job(running.with_state(JobState.RETRYABLE,error=str(exc)))
                self.logger.error('job failed',extra={'job_id':job.id,'symbol':job.symbol})
            else:
                self.state_store.put_job(running.with_state(JobState.COMPLETE,error=None,lease_owner=None,lease_until=None))
        return len(jobs)
    def run(self,poll_seconds=2):
        while not self.lifecycle.stopping:
            self.run_once()
            if self.lifecycle.draining: break
            time.sleep(poll_seconds)
        return 0
