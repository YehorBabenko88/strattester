from __future__ import annotations
from strattester.engine.executor import execute_strategy,require_execution_permission
from strattester.marketdata.sync_engine import DataRequirement as SyncRequirement,SyncEngine,SyncState

class ResearchRunner:
    def __init__(self,store,client,clock_ms=None):
        self.store=store
        self.client=client
        self.clock_ms=clock_ms

    def _sync_definition(self,definition,symbol,start_ms,end_ms):
        engine=SyncEngine(self.store,self.client,clock_ms=self.clock_ms)
        results=[]
        for req in definition.requirements:
            dataset=getattr(req.dataset,'value',req.dataset)
            for tf in (req.timeframes or ('1m',)):
                r=engine.sync_requirement(SyncRequirement(symbol,dataset,tf,start_ms,end_ms))
                results.append((req,r))
                if req.required and r.state is not SyncState.READY:
                    raise RuntimeError(f'required history not ready: {dataset}/{tf}: {r.state.value} {r.message}'.strip())
        return tuple(results)

    def run(self,definition,instrument,*,start_ms:int|None=None,end_ms:int,checkpoint=None,research_permission=None,
            result_store=None,provenance=None,lease_validator=lambda:True,cancelled=lambda:False):
        require_execution_permission(definition,research_permission)
        symbol=instrument['symbol']
        if instrument.get('launchTime') is None:raise ValueError('unknown instrument launch')
        launch=int(instrument['launchTime'])
        launch=((launch+59_999)//60_000)*60_000
        start=launch if start_ms is None else max(launch,int(start_ms))
        if end_ms<start:
            raise ValueError('end_ms precedes instrument availability')
        self._sync_definition(definition,symbol,start,end_ms)
        if result_store is not None:
            from strattester.research.provenance import execute_owned
            return execute_owned(definition,self.store,symbol,start,end_ms,result_store,
                checkpoint=checkpoint,research_permission=research_permission,
                closed_before_ms=self.clock_ms() if self.clock_ms is not None else None,
                lease_validator=lease_validator,cancelled=cancelled,**(provenance or {}))
        return execute_strategy(definition,self.store,symbol,checkpoint=checkpoint,start_ms=start,end_ms=end_ms,research_permission=research_permission,
                                closed_before_ms=self.clock_ms() if self.clock_ms is not None else None)
