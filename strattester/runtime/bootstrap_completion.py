"""Finalize historical bootstrap only when all durable research jobs are terminal."""
from __future__ import annotations
from pathlib import Path
from .phase_manifest import PhaseManifest
from .grid_handoff import write_handoff
from strattester.research.scientific_bootstrap import export_scientific_bootstrap
from strattester.engine.data_first import DataFirstScheduler
from strattester.marketdata.history_planner import PlannedRequirement
from strattester.persistence.data_first_store import digest

class BootstrapCompletionCoordinator:
    def __init__(self,state_store,market_store,root:Path,*,category=None):
        self.state_store=state_store;self.market_store=market_store;self.root=Path(root)
        self.category=category
        self.phase=PhaseManifest(self.root/"state"/"phase-manifest.json")
    def _jobs(self):
        """Adapt durable records directly; never synthesize successful jobs."""
        if callable(getattr(self.state_store,'jobs',None)):
            jobs=list(self.state_store.jobs())
            return [j for j in jobs if self.category is None or
                    j['payload']['instrument']['category']==self.category]
        return list(self.state_store.list_jobs())
    @staticmethod
    def _state(job):
        return job['state'] if isinstance(job,dict) else job.state.value
    def status(self,*,_jobs=None):
        jobs=self._jobs() if _jobs is None else _jobs
        states={}
        for j in jobs:
            state=self._state(j);states[state]=states.get(state,0)+1
        active=sum(1 for j in jobs if self._state(j) not in ('COMPLETE','COMPLETED','FAILED','CANCELLED'))
        failed=states.get('FAILED',0)
        return {"jobs":len(jobs),"active":active,"failed":failed,"states":states,
                "ready_to_finalize":bool(jobs) and all(self._state(j) in ('COMPLETE','COMPLETED') for j in jobs)}
    def finalize_if_ready(self,symbols):
        symbols=list(dict.fromkeys(str(s).upper() for s in symbols))
        jobs=self._jobs();st=self.status(_jobs=jobs)
        if not st["ready_to_finalize"]:return {"finalized":False,**st}
        st={**st,'jobs_completed':True,'ready_to_finalize':False}
        # Legacy Job records do not carry the durable input/result evidence
        # required here. COMPLETE alone must never authorize science handoff.
        actual=[j for j in jobs if isinstance(j,dict) and isinstance(j.get('result'),dict)]
        if len(actual)!=len(jobs):
            return {'finalized':False,'reason':'COMPLETED_RESULT_MISSING',**st}
        present={j['payload']['instrument']['symbol'] for j in actual}
        if not symbols or not set(symbols)<=present:
            return {"finalized":False,'reason':'REQUESTED_JOBS_MISSING',**st}
        categories={j['payload']['instrument']['category'] for j in actual}
        if len(categories)!=1:
            return {'finalized':False,'reason':'AMBIGUOUS_MARKET_CATEGORY',**st}
        for job in actual:
            payload=job['payload'];result=job['result']
            current=next((entry for entry in self.state_store.instruments() if
                          (entry['metadata']['category'],entry['metadata']['symbol'])==
                          (payload['instrument']['category'],payload['instrument']['symbol'])),None)
            if (current is None or current['metadata']!=payload['instrument'] or
                (digest(current['history']) if current['history'] else None)!=payload.get('history_fingerprint')):
                return {'finalized':False,'reason':'COMPLETED_INSTRUMENT_CHANGED',**st}
            if (result.get('instrument')!=payload['instrument'] or
                result.get('requirements')!=payload['requirements'] or
                result.get('fingerprint')!=payload['fingerprint'] or
                result.get('history_provenance')!=payload.get('history_provenance')):
                return {'finalized':False,'reason':'COMPLETED_RESULT_MISMATCH',**st}
            reqs=[PlannedRequirement(**r) for r in payload['requirements']]
            with self.market_store.research_snapshot(payload['instrument']['symbol'],reqs) as snapshot:
                if (any(not DataFirstScheduler._ready(snapshot,r,payload['end_ms']) for r in reqs if r.required) or
                    DataFirstScheduler._data_digest(snapshot,payload)!=result.get('input_sha256')):
                    return {'finalized':False,'reason':'COMPLETED_INPUTS_CHANGED',**st}
        start=min(j['payload']['start_ms'] for j in actual)
        end=max(j['payload']['end_ms'] for j in actual)-1
        science=self.root/"results"/"historical-science-bootstrap.json"
        bundle=export_scientific_bootstrap(self.market_store,symbols,science,start,end)
        if bundle.get('status')!='READY' or any(r.get('status')!='READY' for r in bundle.get('symbols',())):
            return {'finalized':False,'reason':'SCIENTIFIC_DATA_INCOMPLETE','science_bundle':str(science),**st}
        if self._jobs()!=jobs:
            return {'finalized':False,'reason':'JOBS_CHANGED_DURING_FINALIZATION',**st}
        self.phase.advance("HISTORICAL_SCIENCE_BOOTSTRAP",{"jobs":st})
        handoff=self.root/"results"/"grid-handoff.json"
        write_handoff(handoff,science,
                      strategy_results_path=self.root/"results"/"research_results.sqlite3",
                      phase_manifest_path=self.root/"state"/"phase-manifest.json")
        self.phase.advance("GRID_IMPORT",{"science_bundle":str(science),"handoff":str(handoff)})
        return {"finalized":True,"science_bundle":str(science),"handoff":str(handoff),
                "symbols":len(bundle.get("symbols") or ()),**st,'ready_to_finalize':True}
