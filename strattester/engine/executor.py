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
        return self.store.coverage(self.symbol,getattr(dataset,'value',dataset),timeframe)

def requirements_ready(definition,store,symbol):
    for req in definition.requirements:
        dataset=getattr(req.dataset,'value',req.dataset)
        timeframes=req.timeframes or ('1m',)
        if req.required:
            for tf in timeframes:
                if store.coverage(symbol,dataset,tf).count==0:
                    return False
    return True

def execute_strategy(definition,store,symbol,checkpoint=None,start_ms=None,end_ms=None):
    if not requirements_ready(definition,store,symbol):
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
