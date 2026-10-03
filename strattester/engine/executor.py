from dataclasses import dataclass
from strattester.strategies.base import strategy_fingerprint

@dataclass(frozen=True)
class StrategyResult:
    strategy_id:str
    strategy_version:str
    fingerprint:str
    output:object

@dataclass(frozen=True)
class StrategyContext:
    store:object
    symbol:str
    start_ms:int|None=None
    end_ms:int|None=None
    def candles(self,timeframe='1m'):
        return self.store.iter_candles(self.symbol,timeframe,start_ms=self.start_ms,end_ms=self.end_ms)
    def public_trade_aggregates(self,timeframe='1m'):
        return self.store.iter_public_trade_aggregates(
            self.symbol,timeframe,start_ms=self.start_ms,end_ms=self.end_ms)
    def coverage(self,dataset,timeframe='1m'):
        return self.store.coverage(
            self.symbol,getattr(dataset,'value',dataset),timeframe,
            start_ms=self.start_ms,end_ms=self.end_ms)

def _step_ms(timeframe):
    tf=str(timeframe).lower()
    units={'m':60_000,'h':3_600_000,'d':86_400_000}
    try:return int(tf[:-1])*units[tf[-1]]
    except (ValueError,KeyError):return 60_000

def _complete_coverage(cov,start_ms,end_ms,step_ms):
    if cov.count==0:return False
    if start_ms is None or end_ms is None:return True
    if cov.earliest!=start_ms or cov.latest!=end_ms:return False
    if cov.gaps:return False
    return cov.count==((end_ms-start_ms)//step_ms)+1

def requirements_ready(definition,store,symbol,start_ms=None,end_ms=None):
    for req in definition.requirements:
        dataset=getattr(req.dataset,'value',req.dataset)
        timeframes=req.timeframes or ('1m',)
        if req.required:
            for tf in timeframes:
                cov=store.coverage(symbol,dataset,tf,step_ms=_step_ms(tf),start_ms=start_ms,end_ms=end_ms)
                if dataset=='funding':
                    if cov.count==0:return False
                elif not _complete_coverage(cov,start_ms,end_ms,_step_ms(tf)):
                    return False
    return True

def execute_strategy(definition,store,symbol,checkpoint=None,start_ms=None,end_ms=None):
    if not requirements_ready(definition,store,symbol,start_ms=start_ms,end_ms=end_ms):
        raise RuntimeError('strategy requirements are not ready')
    impl=definition.implementation()
    context=StrategyContext(store,symbol,start_ms,end_ms)
    if hasattr(impl,'run_context'):
        output=impl.run_context(context,checkpoint=checkpoint)
    else:
        candle_req=next((r for r in definition.requirements if getattr(r.dataset,'value',r.dataset)=='candles'),None)
        if candle_req is None or not candle_req.timeframes:
            raise RuntimeError('legacy strategy interface requires candle history')
        candles=context.candles(candle_req.timeframes[0])
        output=impl.run(candles,checkpoint=checkpoint)
    return StrategyResult(definition.id,definition.version,strategy_fingerprint(definition),output)
