from dataclasses import dataclass
from strattester.marketdata.timeframes import (
    aligned_window,
    expected_points,
    timeframe_ms,
)
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
    return timeframe_ms(timeframe)

def _coverage_ready(store,symbol,dataset,timeframe,start_ms,end_ms):
    step=_step_ms(timeframe)

    if start_ms is None or end_ms is None:
        cov=store.coverage(
            symbol,
            dataset,
            timeframe,
            step_ms=step,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        return (
            cov.count>0
            and not cov.gaps
        )

    window=aligned_window(
        start_ms,
        end_ms,
        timeframe,
    )

    if window is None:
        return False

    aligned_start,aligned_end=window

    cov=store.coverage(
        symbol,
        dataset,
        timeframe,
        step_ms=step,
        start_ms=aligned_start,
        end_ms=aligned_end,
    )

    if cov.count==0 or cov.gaps:
        return False

    expected=expected_points(
        start_ms,
        end_ms,
        timeframe,
    )

    return (
        cov.count>=expected
        and cov.earliest is not None
        and cov.latest is not None
        and cov.earliest<=aligned_start
        and cov.latest>=aligned_end
    )

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
