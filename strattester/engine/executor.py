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
    try:
        if tf.endswith('m'): return int(tf[:-1])*60_000
        if tf.endswith('h'): return int(tf[:-1])*3_600_000
        if tf.endswith('d'): return int(tf[:-1])*86_400_000
    except ValueError:
        pass
    return 60_000

def _coverage_ready(store,symbol,dataset,timeframe,start_ms,end_ms):
    step=_step_ms(timeframe)
    cov=store.coverage(symbol,dataset,timeframe,step_ms=step,start_ms=start_ms,end_ms=end_ms)
    if cov.count==0 or cov.gaps:
        return False
    if start_ms is None or end_ms is None:
        return True
    if end_ms < start_ms:
        return False
    expected=((int(end_ms)-int(start_ms))//step)+1
    return cov.count>=expected and cov.earliest is not None and cov.latest is not None

def requirements_ready(definition,store,symbol,start_ms=None,end_ms=None):
    for req in definition.requirements:
        dataset=getattr(req.dataset,'value',req.dataset)
        timeframes=req.timeframes or ('1m',)
        if req.required:
            for tf in timeframes:
                if not _coverage_ready(store,symbol,dataset,tf,start_ms,end_ms):
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
