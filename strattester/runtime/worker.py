from __future__ import annotations
import time,uuid,threading
from strattester.engine.jobs import JobState

class WorkerRuntime:
    def __init__(self,state_store,scheduler,executor,lifecycle,logger,snapshot_provider,worker_id=None,
                 lease_seconds=300,lease_heartbeat_seconds=None,node_id=None):
        self.state_store=state_store; self.scheduler=scheduler; self.executor=executor; self.lifecycle=lifecycle; self.logger=logger; self.snapshot_provider=snapshot_provider
        self.worker_id=worker_id or f'worker-{uuid.uuid4()}'; self.lease_seconds=lease_seconds
        self.lease_heartbeat_seconds=lease_heartbeat_seconds or max(1,min(60,lease_seconds/3))
        self.node_id=node_id

    def _execute_with_lease(self,job):
        done=threading.Event(); box={}
        def target():
            try: box['result']=self.executor(job)
            except BaseException as exc: box['error']=exc
            finally: done.set()
        t=threading.Thread(target=target,name=f'job-{job.id}',daemon=True)
        t.start()
        lease_ok=True
        while not done.wait(self.lease_heartbeat_seconds):
            try:
                lease_ok=self.state_store.renew_lease(
                    job.id,self.worker_id,job.lease_token,self.lease_seconds)
            except Exception:
                self.logger.exception('lease renewal failed',extra={'job_id':job.id,'symbol':job.symbol})
                lease_ok=False
            if not lease_ok:
                self.logger.error('job lease lost; stale worker result will be fenced',
                                  extra={'job_id':job.id,'symbol':job.symbol})
                break
        if not done.is_set():
            done.wait()
        return lease_ok,box

    def run_once(self):
        if self.lifecycle.draining or self.lifecycle.stopping:return 0
        candidates=self.scheduler.ready_jobs(self.snapshot_provider())
        if self.node_id is not None:
            candidates=[j for j in candidates if j.target_node in (None,self.node_id)]
        if not candidates:return 0
        jobs=self.state_store.claim_ready_jobs(
            self.worker_id,limit=len(candidates),lease_seconds=self.lease_seconds,
            job_ids=[j.id for j in candidates],node_id=self.node_id)
        for job in jobs:
            started=self.state_store.transition_claimed(
                job.id,self.worker_id,job.lease_token,JobState.RUNNING,
                attempts=job.attempts+1)
            if not started:
                continue
            running=self.state_store.get_job(job.id)
            lease_ok,box=self._execute_with_lease(running)
            if 'error' in box:
                exc=box['error']
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,JobState.RETRYABLE,
                    error=str(exc),lease_owner=None,lease_until=None)
                self.logger.error('job failed',extra={'job_id':job.id,'symbol':job.symbol})
            elif lease_ok:
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,JobState.COMPLETE,
                    error=None,lease_owner=None,lease_until=None)
        return len(jobs)

    def run(self,poll_seconds=2):
        while not self.lifecycle.stopping:
            self.run_once()
            if self.lifecycle.draining: break
            time.sleep(poll_seconds)
        return 0
