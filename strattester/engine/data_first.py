"""Explicit data-first research orchestration; no order/credential capability."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict
import hashlib
import json
import threading
import time
import uuid
from strattester.engine.executor import execute_strategy,_coverage_ready
from strattester.marketdata.history_planner import HistoryPlanner,PlannedRequirement,CATEGORIES
from strattester.marketdata.sync_engine import SyncEngine,DataRequirement as SyncRequirement
from strattester.persistence.data_first_store import canonical,digest
from strattester.strategies.base import strategy_fingerprint
from strattester.engine.resource_manager import decide_resources

class RateLimiter:
    def __init__(self,requests_per_second=2,*,clock=time.monotonic,sleep=time.sleep):
        if type(requests_per_second) not in (int,float) or not 0<requests_per_second<=20:
            raise ValueError('request rate budget')
        self.interval=1/requests_per_second;self.clock=clock;self.sleep=sleep
        self.lock=threading.Lock();self.next=0.

    def wait(self,cancel):
        while True:
            if cancel():raise InterruptedError('scheduler cancelled')
            with self.lock:
                now=self.clock();delay=self.next-now
                if delay<=0:self.next=now+self.interval;return
            self.sleep(min(delay,.05))

class DataFirstScheduler:
    """Factories open dedicated clients and market stores inside each worker.

    The state DB is separate. Per-category store identity must be distinct.
    Cooperative limits do not sandbox arbitrary strategy implementations.
    """
    def __init__(self,state,registry,client_factory,store_factory,*,categories=('linear',),
                 max_concurrency=2,max_jobs_per_tick=16,max_pages_per_job=1,
                 max_observations=100000,requests_per_second=2,lease_ms=60000,
                 max_tick_seconds=30,clock_ms=None,monotonic=time.monotonic,
                 sleep=time.sleep,cancel=lambda:False,resource_admission=lambda:True,snapshot_provider=None):
        if not categories or len(set(categories))!=len(categories) or any(c not in CATEGORIES for c in categories):raise ValueError('market categories')
        for value,maximum in ((max_concurrency,8),(max_jobs_per_tick,1000),(max_pages_per_job,100)):
            if type(value) is not int or not 1<=value<=maximum:raise ValueError('scheduler concurrency/page budget')
        if type(lease_ms) is not int or not 1<=max_tick_seconds<=300 or not max_tick_seconds*1000<lease_ms<=600000:raise ValueError('lease/runtime budget')
        self.state=state;self.registry=registry;self.client_factory=client_factory;self.store_factory=store_factory
        self.categories=tuple(categories);self.max_concurrency=max_concurrency;self.max_jobs=max_jobs_per_tick
        self.max_pages=max_pages_per_job;self.lease_ms=lease_ms;self.max_tick_seconds=max_tick_seconds
        self.clock_ms=clock_ms or (lambda:int(time.time()*1000));self.monotonic=monotonic
        self.external_cancel=cancel;self.resource_admission=resource_admission
        self.snapshot_provider=snapshot_provider
        self.limiter=RateLimiter(requests_per_second,clock=monotonic,sleep=sleep)
        self.planner=HistoryPlanner(max_observations);self.owner='data-first-'+uuid.uuid4().hex
        self._market_paths={};self._path_lock=threading.Lock()

    def _client(self,category,cancel):
        client=self.client_factory(category)
        previous=getattr(client,'before_request',None)
        def gate():
            self.limiter.wait(cancel)
            if previous:previous()
        client.before_request=gate;client.cancel=cancel
        return client

    @staticmethod
    def _close_client(client):
        session=getattr(client,'session',None)
        if session is not None and hasattr(session,'close'):session.close()

    def discover(self):
        """Publish only fully paginated category snapshots, never partial pages."""
        for category in self.categories:
            client=self._client(category,self.external_cancel)
            try:rows=client.fetch_instruments(category,max_pages=100,max_instruments=20000)
            finally:self._close_client(client)
            old=[i for i in self.state.instruments((category,)) if i['metadata']['status']=='Trading']
            if old and (not rows or len(rows)<len(old)/2):raise RuntimeError('suspicious incomplete universe snapshot')
            self.state.snapshot(category,rows,self.clock_ms())
        return self.state.instruments(self.categories)

    def plan(self,*,start_ms,end_ms):
        keys=[]
        for entry in self.state.instruments(self.categories):
            instrument=entry['metadata'];history=entry['history']
            intervals=history['intervals'] if history else [(start_ms,end_ms)]
            for lower,upper in intervals:
                lo=max(start_ms,lower);hi=min(end_ms,upper)
                if hi<=lo:continue
                for definition in self.registry.discover():
                    if definition.enabled is not True:continue
                    plan=self.planner.plan(definition,instrument,start_ms=lo,end_ms=hi,now_ms=self.clock_ms())
                    payload=dict(instrument=instrument,strategy_id=definition.id,strategy_version=definition.version,
                        fingerprint=strategy_fingerprint(definition),start_ms=plan.start_ms,end_ms=plan.end_exclusive_ms,
                        requirements=[r.json() for r in plan.requirements],blockers=plan.blockers,
                        history_provenance=history['source_sha256'] if history else None,
                        history_fingerprint=digest(history) if history else None,
                        activity_basis='EXPLICIT_ARCHIVE_INTERVALS' if history else 'LAUNCH_DELIVERY_BOUNDS_ONLY')
                    keys.append(self.state.plan(payload,self.clock_ms()))
        return tuple(keys)

    def _definition(self,payload):
        found=[d for d in self.registry.discover() if (d.id,d.version)==(payload['strategy_id'],payload['strategy_version'])]
        if len(found)!=1 or found[0].enabled is not True or strategy_fingerprint(found[0])!=payload['fingerprint']:
            raise ValueError('strategy disabled or changed after planning')
        return found[0]

    def _open_store(self,category):
        store=self.store_factory(category)
        try:store.bind_market_category(category)
        except BaseException:store.close();raise
        path=getattr(store,'root',getattr(store,'path',None))
        if path is None:
            store.close();raise ValueError('explicit market storage identity required')
        path=str(path.resolve())
        with self._path_lock:
            if any(c!=category and p==path for c,p in self._market_paths.items()):
                store.close();raise ValueError('market type storage alias')
            self._market_paths[category]=path
        return store

    def _current_matches(self,payload):
        entry=next((i for i in self.state.instruments(self.categories)
                    if (i['metadata']['category'],i['metadata']['symbol'])==
                    (payload['instrument']['category'],payload['instrument']['symbol'])),None)
        return (entry is not None and entry['metadata']==payload['instrument']
                and (digest(entry['history']) if entry['history'] else None)==payload['history_fingerprint'])

    @staticmethod
    def _ready(store,req,closed_before):
        return _coverage_ready(store,req.symbol,req.dataset,req.timeframe,req.start_ms,req.end_ms,
                               req.min_observations,closed_before)

    @staticmethod
    def _data_digest(store,payload):
        # SQLite read transactions and routed stores remain authoritative.
        # Bind all values, not only row counts, so mutation during execution fails.
        if not hasattr(store,'range_fingerprint'):raise ValueError('data fingerprint contract unavailable')
        return digest([store.range_fingerprint(PlannedRequirement(**r)) for r in payload['requirements'] if r['required']])

    def _process(self,key,deadline):
        token=self.state.claim(key,self.owner,self.clock_ms(),self.lease_ms,self.max_concurrency)
        if token is None:return self.state.get(key)
        job=self.state.get(key);payload=job['payload'];store=None;client=None;execution_started=False
        def transition(status,**kwargs):
            self.state.transition(key,self.owner,token,self.clock_ms(),status,**kwargs)
        resource_check=[self.monotonic()+1.]
        def cancelled():
            if self.external_cancel() or self.monotonic()>=deadline:return True
            if self.snapshot_provider is not None and self.monotonic()>=resource_check[0]:
                resource_check[0]=self.monotonic()+1.
                if not decide_resources(self.snapshot_provider()).allow_heavy:return True
            return False
        def progress(value):
            self.state.renew(key,self.owner,token,self.clock_ms(),self.lease_ms)
            transition('SYNCING',progress={'last_page':value})
        try:
            definition=self._definition(payload)
            if not self._current_matches(payload):
                transition('BLOCKED',reason='INSTRUMENT_METADATA_CHANGED',release=True);return self.state.get(key)
            if payload['blockers']:
                transition('BLOCKED',reason=';'.join(payload['blockers']),release=True);return self.state.get(key)
            if cancelled():
                transition('PARTIAL',reason='CANCELLED_OR_RESOURCE_DEADLINE',release=True);return self.state.get(key)
            store=self._open_store(payload['instrument']['category'])
            client=self._client(payload['instrument']['category'],cancelled)
            reqs=[PlannedRequirement(**r) for r in payload['requirements']]
            pending=[r for r in reqs if r.required and not self._ready(store,r,payload['end_ms'])]
            pages_left=self.max_pages
            for req in pending:
                if cancelled() or pages_left<=0:break
                transition('SYNCING')
                page_progress=[]
                def checkpoint(value):page_progress.append(value);progress(value)
                engine=SyncEngine(store,client,clock_ms=self.clock_ms,category=payload['instrument']['category'],
                                  max_pages=pages_left,cancel=cancelled,checkpoint=checkpoint)
                synced=engine.sync_requirement(SyncRequirement(req.symbol,req.dataset,req.timeframe,req.start_ms,req.end_ms))
                pages_left-=len(page_progress)
                if synced.rejected:
                    transition('BLOCKED',reason='REJECTED_MARKET_DATA',release=True);return self.state.get(key)
                if synced.state.value in ('REPAIR_REQUIRED','UNAVAILABLE','DEGRADED'):
                    transition('BLOCKED',reason='SYNC_'+synced.state.value,release=True);return self.state.get(key)
            if cancelled() or any(not self._ready(store,r,payload['end_ms']) for r in reqs if r.required):
                transition('PARTIAL',reason='REQUIRED_HISTORY_INCOMPLETE_OR_CANCELLED',release=True);return self.state.get(key)
            with store.research_snapshot(payload['instrument']['symbol'],reqs) as snapshot:
                if any(not self._ready(snapshot,r,payload['end_ms']) for r in reqs if r.required):
                    transition('PARTIAL',reason='SNAPSHOT_NOT_READY',release=True);return self.state.get(key)
                transition('READY')
                if not self.resource_admission():
                    transition('READY',reason='RESOURCE_ADMISSION_BLOCKED',release=True);return self.state.get(key)
                definition=self._definition(payload)
                if not self._current_matches(payload):
                    transition('BLOCKED',reason='HISTORY_CHANGED_AFTER_PLANNING',release=True);return self.state.get(key)
                source_digest=self._data_digest(snapshot,payload)
                self.state.renew(key,self.owner,token,self.clock_ms(),self.lease_ms)
                transition('RUNNING',progress={'input_sha256':source_digest})
                execution_started=True
                definition=self._definition(payload)
                result=execute_strategy(definition,snapshot,payload['instrument']['symbol'],
                    start_ms=payload['start_ms'],end_ms=payload['end_ms']-1,cancel=cancelled,closed_before_ms=payload['end_ms'])
                if cancelled():
                    transition('BLOCKED',reason='EXECUTION_CANCELLED_RESULT_NOT_PUBLISHED',release=True);return self.state.get(key)
                if self._data_digest(snapshot,payload)!=source_digest:
                    transition('BLOCKED',reason='DATA_CHANGED_DURING_EXECUTION',release=True);return self.state.get(key)
                self._definition(payload)
                if not self._current_matches(payload):
                    transition('BLOCKED',reason='HISTORY_CHANGED_DURING_EXECUTION',release=True);return self.state.get(key)
                published=dict(strategy_id=result.strategy_id,strategy_version=result.strategy_version,
                    fingerprint=result.fingerprint,output=result.output,input_sha256=source_digest,
                    instrument=payload['instrument'],requirements=payload['requirements'],activity_basis=payload['activity_basis'],
                    history_provenance=payload['history_provenance'],trading='NO-GO',physical_g1='NOT_AUTHORIZED')
                canonical(published)
                transition('COMPLETED',result=published,release=True)
        except InterruptedError:
            transition('BLOCKED' if execution_started else 'PARTIAL',
                       reason='UNCERTAIN_INTERRUPTED_EXECUTION' if execution_started else 'CANCELLED',release=True)
        except Exception as exc:
            # Stable error codes; no credentials/URLs or arbitrary exception text.
            try:transition('FAILED',reason=type(exc).__name__ if type(exc).__name__ in ('ValueError','RuntimeError','DatabaseError') else 'EXECUTION_ERROR',release=True)
            except RuntimeError:pass # lost lease cannot publish any stale result
        finally:
            if store is not None:store.close()
            if client is not None:self._close_client(client)
        return self.state.get(key)

    def tick(self):
        if self.external_cancel() or not self.resource_admission():return ()
        active_limit=self.max_concurrency
        if self.snapshot_provider is not None:
            decision=decide_resources(self.snapshot_provider())
            if not decision.allow_heavy:return ()
            active_limit=min(active_limit,decision.max_new_jobs)
        deadline=self.monotonic()+self.max_tick_seconds
        now=self.clock_ms()
        candidates=[j for j in self.state.jobs() if j['state'] not in ('COMPLETED','BLOCKED','FAILED')
                    and (j['lease_until'] is None or j['lease_until']<=now)]
        candidates.sort(key=lambda j:(j['state']!='READY',j['last_event'],j['id']))
        selected=candidates[:self.max_jobs]
        results=[]
        with ThreadPoolExecutor(max_workers=active_limit) as pool:
            futures=[pool.submit(self._process,j['id'],deadline) for j in selected]
            for future in as_completed(futures):results.append(future.result())
        return tuple(results)
