from dataclasses import dataclass
import re
import time
from strattester.strategies.base import strategy_fingerprint

@dataclass(frozen=True)
class StrategyResult:
    strategy_id:str
    strategy_version:str
    fingerprint:str
    output:object

@dataclass(frozen=True)
class ResearchExecutionPermit:
    strategy_id:str
    version:str
    fingerprint:str
    reason:str
    @classmethod
    def for_strategy(cls,definition,*,reason):
        if type(reason) is not str or not reason.strip() or len(reason)>256:
            raise ValueError('explicit research reason required')
        return cls(definition.id,definition.version,strategy_fingerprint(definition),reason)

@dataclass(frozen=True)
class StrategyContext:
    store:object
    symbol:str
    start_ms:int|None=None
    end_ms:int|None=None
    requirements:tuple=()
    cancel:object=lambda:False
    closed_before_ms:int|None=None
    def candles(self,timeframe='1m'):
        start,end=self._window('candles',timeframe)
        for row in self.store.iter_candles(self.symbol,timeframe,start_ms=start,end_ms=end):
            if self.cancel():raise InterruptedError('research cancelled')
            yield row
    def public_trade_aggregates(self,timeframe='1m'):
        start,end=self._window('public_trade_aggregates',timeframe)
        for row in self.store.iter_public_trade_aggregates(self.symbol,timeframe,start_ms=start,end_ms=end):
            if self.cancel():raise InterruptedError('research cancelled')
            yield row
    def coverage(self,dataset,timeframe='1m'):
        start,end=self._window(getattr(dataset,'value',dataset),timeframe)
        return self.store.coverage(
            self.symbol,getattr(dataset,'value',dataset),timeframe,
            step_ms=_step_ms(timeframe),start_ms=start,end_ms=end)
    def _window(self,dataset,timeframe):
        req=next((r for r in self.requirements if getattr(r.dataset,'value',r.dataset)==dataset and timeframe in (r.timeframes or ('1m',))),None)
        return _requirement_window(req,self.start_ms,self.end_ms,timeframe,self.closed_before_ms)

def _step_ms(timeframe):
    tf=str(timeframe).lower()
    if re.fullmatch('[1-9][0-9]{0,4}[mhd]',tf) is None:raise ValueError('unsupported timeframe')
    return int(tf[:-1])*{'m':60_000,'h':3_600_000,'d':86_400_000}[tf[-1]]

def _requirement_window(req,start,end,timeframe,closed_before_ms=None):
    step=_step_ms(timeframe)
    if start is not None:start=((start+step-1)//step)*step
    if end is not None:end=(end//step)*step
    if end is not None and closed_before_ms is not None:end=min(end,((closed_before_ms-step)//step)*step)
    if req is not None and req.lookback_ms is not None and end is not None:
        lower=((end+step-req.lookback_ms+step-1)//step)*step
        start=lower if start is None else max(start,lower)
    return start,end

def _coverage_ready(store,symbol,dataset,timeframe,start_ms,end_ms,minimum=1,closed_before_ms=None):
    if dataset in ('funding','public_trades','orderbook_l2','liquidations'):
        # Fixed-rate or aggregated-row counts do not establish event history.
        return False
    step=_step_ms(timeframe)
    cov=store.coverage(symbol,dataset,timeframe,step_ms=step,start_ms=start_ms,end_ms=end_ms)
    if cov.count<minimum or cov.gaps or cov.earliest is None or cov.latest is None:
        return False
    start_ms=cov.earliest if start_ms is None else start_ms
    end_ms=cov.latest if end_ms is None else end_ms
    if end_ms < start_ms:
        return False
    if start_ms%step or end_ms%step or cov.earliest!=start_ms or cov.latest!=end_ms:return False
    closed_before_ms=int(time.time()*1000) if closed_before_ms is None else closed_before_ms
    if end_ms+step>closed_before_ms:return False
    expected=((int(end_ms)-int(start_ms))//step)+1
    if cov.count!=expected:return False
    validator=getattr(store,'validate_range',None)
    return validator is not None and validator(symbol,dataset,timeframe,start_ms,end_ms,step)

def requirements_ready(definition,store,symbol,start_ms=None,end_ms=None,closed_before_ms=None):
    for req in definition.requirements:
        dataset=getattr(req.dataset,'value',req.dataset)
        timeframes=req.timeframes or ('1m',)
        if req.required:
            for tf in timeframes:
                start,end=_requirement_window(req,start_ms,end_ms,tf,closed_before_ms)
                if not _coverage_ready(store,symbol,dataset,tf,start,end,req.min_observations,closed_before_ms):
                    return False
    return True

def require_execution_permission(definition,research_permission=None):
    if definition.enabled is not True:
        permit=research_permission
        if (type(permit) is not ResearchExecutionPermit or not permit.reason.strip() or
            (permit.strategy_id,permit.version,permit.fingerprint)!=(definition.id,definition.version,strategy_fingerprint(definition))):
            raise ValueError('disabled strategy: explicit research context permission required')

def execute_strategy(definition,store,symbol,checkpoint=None,start_ms=None,end_ms=None,*,research_permission=None,cancel=lambda:False,closed_before_ms=None):
    require_execution_permission(definition,research_permission)
    if cancel():raise InterruptedError('research cancelled')
    if any(req.required for req in definition.requirements) and not getattr(store,'research_snapshot_active',False):
        factory=getattr(store,'research_snapshot',None)
        if factory is None:raise RuntimeError('coherent research snapshot unavailable')
        with factory(symbol,definition.requirements) as snapshot:
            return execute_strategy(definition,snapshot,symbol,checkpoint,start_ms,end_ms,
                research_permission=research_permission,cancel=cancel,closed_before_ms=closed_before_ms)
    if not requirements_ready(definition,store,symbol,start_ms=start_ms,end_ms=end_ms,closed_before_ms=closed_before_ms):
        raise RuntimeError('strategy requirements are not ready')
    impl=definition.implementation()
    context=StrategyContext(store,symbol,start_ms,end_ms,definition.requirements,cancel,closed_before_ms)
    if hasattr(impl,'run_context'):
        output=impl.run_context(context,checkpoint=checkpoint)
    else:
        candle_req=next((r for r in definition.requirements if getattr(r.dataset,'value',r.dataset)=='candles'),None)
        if candle_req is None or not candle_req.timeframes:
            raise RuntimeError('legacy strategy interface requires candle history')
        candles=context.candles(candle_req.timeframes[0])
        output=impl.run(candles,checkpoint=checkpoint)
    return StrategyResult(definition.id,definition.version,strategy_fingerprint(definition),output)
