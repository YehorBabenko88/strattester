from __future__ import annotations
import time
from strattester.engine.jobs import JobState
class WorkerRuntime:
    def __init__(self,state_store,scheduler,executor,lifecycle,logger,snapshot_provider):
        self.state_store=state_store; self.scheduler=scheduler; self.executor=executor; self.lifecycle=lifecycle; self.logger=logger; self.snapshot_provider=snapshot_provider
    def run_once(self):
        jobs=self.scheduler.ready_jobs(self.snapshot_provider())
        if self.lifecycle.draining or self.lifecycle.stopping:return 0
        for job in jobs:
            running=job.with_state(JobState.RUNNING,attempts=job.attempts+1)
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
