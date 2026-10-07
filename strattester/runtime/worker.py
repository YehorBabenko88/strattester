from __future__ import annotations
import concurrent.futures,pickle,time,uuid
from strattester.engine.jobs import JobState

def _invoke_executor(executor,job):
    return executor(job)

class WorkerRuntime:
    def __init__(self,state_store,scheduler,executor,lifecycle,logger,snapshot_provider,worker_id=None,
                 lease_seconds=300,lease_heartbeat_seconds=None,node_id=None,execution_mode='auto'):
        self.state_store=state_store; self.scheduler=scheduler; self.executor=executor; self.lifecycle=lifecycle; self.logger=logger; self.snapshot_provider=snapshot_provider
        self.worker_id=worker_id or f'worker-{uuid.uuid4()}'; self.lease_seconds=lease_seconds
        self.lease_heartbeat_seconds=lease_heartbeat_seconds or max(1,min(60,lease_seconds/3))
        self.node_id=node_id
        self.execution_mode=execution_mode

    def _pool_kind(self):
        if self.execution_mode=='thread': return 'thread'
        try:
            pickle.dumps(self.executor)
        except Exception:
            if self.execution_mode=='process':
                raise RuntimeError('process execution requested but executor is not serializable')
            return 'thread'
        return 'process'

    def _finish_future(self,job,future,lease_valid):
        try:
            future.result()
        except BaseException as exc:
            if lease_valid:
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,JobState.RETRYABLE,
                    error=str(exc),lease_owner=None,lease_until=None)
            self.logger.error('job failed',extra={'job_id':job.id,'symbol':job.symbol})
        else:
            if lease_valid:
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,JobState.COMPLETE,
                    error=None,lease_owner=None,lease_until=None)

    def _run_parallel(self,jobs):
        kind=self._pool_kind()
        pool_cls=concurrent.futures.ProcessPoolExecutor if kind=='process' else concurrent.futures.ThreadPoolExecutor
        lease_valid={j.id:True for j in jobs}
        self.logger.info('parallel batch started',extra={'jobs':len(jobs),'mode':kind})
        with pool_cls(max_workers=max(1,len(jobs))) as pool:
            futures={pool.submit(_invoke_executor,self.executor,j):j for j in jobs}
            pending=set(futures)
            while pending:
                done,pending=concurrent.futures.wait(
                    pending,timeout=self.lease_heartbeat_seconds,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                for f in done:
                    j=futures[f]
                    self._finish_future(j,f,lease_valid[j.id])
                if pending:
                    for f in tuple(pending):
                        j=futures[f]
                        if not lease_valid[j.id]: continue
                        try:
                            ok=self.state_store.renew_lease(
                                j.id,self.worker_id,j.lease_token,self.lease_seconds)
                        except Exception:
                            self.logger.exception('lease renewal failed',extra={'job_id':j.id,'symbol':j.symbol})
                            ok=False
                        if not ok:
                            lease_valid[j.id]=False
                            self.logger.error(
                                'job lease lost; stale result fenced',
                                extra={'job_id':j.id,'symbol':j.symbol})
        return len(jobs)

    def run_once(self):
        if self.lifecycle.draining or self.lifecycle.stopping:return 0
        snapshot=self.snapshot_provider()
        candidates=self.scheduler.ready_jobs(snapshot)
        if self.node_id is not None:
            candidates=[j for j in candidates if j.target_node in (None,self.node_id)]
        if not candidates:return 0
        jobs=self.state_store.claim_ready_jobs(
            self.worker_id,limit=len(candidates),lease_seconds=self.lease_seconds,
            job_ids=[j.id for j in candidates],node_id=self.node_id)
        running=[]
        for job in jobs:
            started=self.state_store.transition_claimed(
                job.id,self.worker_id,job.lease_token,JobState.RUNNING,
                attempts=job.attempts+1)
            if started:
                running.append(self.state_store.get_job(job.id))
        if running:
            self._run_parallel(running)
        return len(running)

    def run(self,poll_seconds=2):
        while not self.lifecycle.stopping:
            self.run_once()
            if self.lifecycle.draining: break
            time.sleep(poll_seconds)
        return 0
