from __future__ import annotations
from strattester.engine.executor import execute_strategy
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

    def run(self,definition,instrument,*,start_ms:int|None=None,end_ms:int,checkpoint=None):
        symbol=instrument['symbol']
        launch=int(instrument.get('launchTime') or 0)
        launch=(launch//60_000)*60_000
        start=launch if start_ms is None else max(launch,int(start_ms))
        if end_ms<start:
            raise ValueError('end_ms precedes instrument availability')
        self._sync_definition(definition,symbol,start,end_ms)
        return execute_strategy(definition,self.store,symbol,checkpoint=checkpoint)
