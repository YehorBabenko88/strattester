from dataclasses import dataclass
from strattester.strategies.base import strategy_fingerprint

@dataclass(frozen=True)
class StrategyResult:
    strategy_id:str
    strategy_version:str
    fingerprint:str
    output:object

def requirements_ready(definition,store,symbol):
    for req in definition.requirements:
        if getattr(req.dataset,'value',req.dataset)=='candles':
            for tf in req.timeframes:
                if store.coverage(symbol,'candles',tf).count==0: return False
        elif req.required:
            return False
    return True

def execute_strategy(definition,store,symbol,checkpoint=None):
    if not requirements_ready(definition,store,symbol):
        raise RuntimeError('strategy requirements are not ready')
    impl=definition.implementation()
    candles=store.iter_candles(symbol,definition.requirements[0].timeframes[0])
    output=impl.run(candles,checkpoint=checkpoint)
    return StrategyResult(definition.id,definition.version,strategy_fingerprint(definition),output)
