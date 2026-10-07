from __future__ import annotations
import concurrent.futures,pickle,time,uuid,errno,sqlite3
from strattester.engine.jobs import JobState
from strattester.runtime.cluster_recovery import ClusterRecovery

def _invoke_executor(executor,job):
    return executor(job)

class WorkerRuntime:
    def __init__(self,state_store,scheduler,executor,lifecycle,logger,snapshot_provider,worker_id=None,
                 lease_seconds=300,lease_heartbeat_seconds=None,node_id=None,execution_mode='auto',max_attempts=5,background_tasks=None,resources=None):
        self.state_store=state_store; self.scheduler=scheduler; self.executor=executor; self.lifecycle=lifecycle; self.logger=logger; self.snapshot_provider=snapshot_provider
        self.worker_id=worker_id or f'worker-{uuid.uuid4()}'; self.lease_seconds=lease_seconds
        self.lease_heartbeat_seconds=lease_heartbeat_seconds or max(1,min(60,lease_seconds/3))
        self.node_id=node_id
        self.execution_mode=execution_mode
        self.max_attempts=max(1,int(max_attempts))
        self.cluster_recovery=ClusterRecovery(state_store) if hasattr(state_store,'live_nodes') else None
        self.control_plane_healthy=True
        self.resource_exhausted=False
        self.node_generation=None
        self.background_tasks=list(background_tasks or ())
        self.resources=list(resources or ())

    def _heartbeat_node(self):
        if self.node_id is not None and hasattr(self.state_store,'heartbeat_node'):
            try:
                if self.node_generation is None and hasattr(self.state_store,'register_node_generation'):
                    self.node_generation=self.state_store.register_node_generation(
                        self.node_id,meta={'worker_id':self.worker_id})
                kwargs={'meta':{'worker_id':self.worker_id,'generation':self.node_generation}}
                if self.node_generation is not None:kwargs['generation']=self.node_generation
                ok=self.state_store.heartbeat_node(self.node_id,**kwargs)
                if ok is False:raise RuntimeError('node generation fenced')
            except Exception:
                self.control_plane_healthy=False
                if hasattr(self.state_store,'reconnect'):
                    try: self.state_store.reconnect()
                    except Exception: pass
                self.logger.exception('node heartbeat failed',extra={'node_id':self.node_id})
            else:
                self.control_plane_healthy=True

    def _pool_kind(self):
        if self.execution_mode=='thread': return 'thread'
        try:
            pickle.dumps(self.executor)
        except Exception:
            if self.execution_mode=='process':
                raise RuntimeError('process execution requested but executor is not serializable')
            return 'thread'
        return 'process'

    @staticmethod
    def _is_resource_exhaustion(exc):
        if isinstance(exc,OSError) and getattr(exc,'errno',None) in (errno.ENOSPC,errno.EDQUOT):
            return True
        text=str(exc).lower()
        return isinstance(exc,sqlite3.Error) and any(x in text for x in ('database or disk is full','disk i/o error'))

    def clear_resource_exhaustion(self):
        self.resource_exhausted=False

    def _finish_future(self,job,future,lease_valid):
        try:
            future.result()
        except BaseException as exc:
            exhausted=self._is_resource_exhaustion(exc)
            if exhausted:self.resource_exhausted=True
            if lease_valid:
                terminal=exhausted or job.attempts>=self.max_attempts
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,
                    JobState.FAILED if terminal else JobState.RETRYABLE,
                    error=str(exc),lease_owner=None,lease_until=None)
            self.logger.error('job failed',extra={'job_id':job.id,'symbol':job.symbol,'attempts':job.attempts})
        else:
            if lease_valid:
                self.state_store.transition_claimed(
                    job.id,self.worker_id,job.lease_token,JobState.COMPLETE,
                    error=None,lease_owner=None,lease_until=None)

    def _run_parallel(self,jobs):
        kind=self._pool_kind()
        pool_cls=concurrent.futures.ProcessPoolExecutor if kind=='process' else concurrent.futures.ThreadPoolExecutor
        lease_valid={j.id:True for j in jobs}
        self._heartbeat_node()
        self.logger.info('parallel batch started',extra={'jobs':len(jobs),'mode':kind})
        with pool_cls(max_workers=max(1,len(jobs))) as pool:
            futures={}
            for j in jobs:
                try:
                    futures[pool.submit(_invoke_executor,self.executor,j)]=j
                except BaseException as exc:
                    self.state_store.transition_claimed(
                        j.id,self.worker_id,j.lease_token,JobState.RETRYABLE,
                        error=f'worker pool submission failed: {exc}',lease_owner=None,lease_until=None)
                    self.logger.error('worker pool submission failed',extra={'job_id':j.id,'symbol':j.symbol})
            if not futures:
                return len(jobs)
            pending=set(futures)
            while pending:
                done,pending=concurrent.futures.wait(
                    pending,timeout=self.lease_heartbeat_seconds,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                for f in done:
                    j=futures[f]
                    self._finish_future(j,f,lease_valid[j.id])
                if pending:
                    self._heartbeat_node()
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
        if self.lifecycle.draining or self.lifecycle.stopping or self.resource_exhausted:return 0
        self._heartbeat_node()
        if self.node_id is not None and hasattr(self.state_store,'heartbeat_node') and not self.control_plane_healthy:
            self.logger.error('control plane unavailable; refusing new work',extra={'node_id':self.node_id})
            return 0
        if self.cluster_recovery is not None:
            try:
                self.cluster_recovery.reconcile()
            except Exception:
                self.logger.exception('cluster recovery failed')
        for task in self.background_tasks:
            try: task.maybe_run()
            except Exception: self.logger.exception('background task failed')
        snapshot=self.snapshot_provider()
        try:
            candidates=self.scheduler.ready_jobs(snapshot,node_id=self.node_id)
        except TypeError:
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

    def close(self):
        errors=[]
        resources=self.resources
        self.resources=[]
        for resource in reversed(resources):
            try: resource.close()
            except Exception as exc: errors.append(exc)
        if errors: raise errors[0]

    def run(self,poll_seconds=2):
        try:
            while not self.lifecycle.stopping:
                self.run_once()
                if self.lifecycle.draining: break
                time.sleep(poll_seconds)
            return 0
        finally:
            self.close()
