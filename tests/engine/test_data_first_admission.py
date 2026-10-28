import pytest
from strattester.engine.executor import execute_strategy
from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle
from strattester.strategies.base import DataRequirement,StrategyDefinition

class Count:
    calls=0
    def run(self,candles,checkpoint=None):
        type(self).calls+=1
        return sum(1 for _ in candles)

def test_disabled_executor_requires_explicit_bound_research_permission(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        store.upsert_candles([Candle('X','1m',0,1,1,1,1,1)])
        d=StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count,enabled=False)
        before=Count.calls
        with pytest.raises(ValueError,match='disabled'):
            execute_strategy(d,store,'X')
        assert Count.calls==before
    finally:store.close()

def test_minimum_observations_is_mandatory(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        store.upsert_candles([Candle('X','1m',0,1,1,1,1,1)])
        d=StrategyDefinition('count','1',(DataRequirement('candles',('1m',),min_observations=2),),Count)
        with pytest.raises(RuntimeError):execute_strategy(d,store,'X')
    finally:store.close()

def test_off_grid_density_does_not_satisfy_coverage(tmp_path):
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        store.upsert_candles([Candle('X','1m',t,1,1,1,1,1) for t in (1,60000)])
        d=StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count)
        with pytest.raises(RuntimeError):execute_strategy(d,store,'X',start_ms=0,end_ms=60000)
    finally:store.close()

def test_bound_research_permission_never_skips_data_requirements(tmp_path):
    from strattester.engine.executor import ResearchExecutionPermit
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        d=StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count,enabled=False)
        permit=ResearchExecutionPermit.for_strategy(d,reason='synthetic regression')
        with pytest.raises(RuntimeError):execute_strategy(d,store,'X',research_permission=permit)
        store.upsert_candles([Candle('X','1m',0,1,1,1,1,1)])
        assert execute_strategy(d,store,'X',research_permission=permit).output==1
        other=StrategyDefinition('other','1',d.requirements,Count,enabled=False)
        with pytest.raises(ValueError):execute_strategy(other,store,'X',research_permission=permit)
    finally:store.close()

def test_disabled_runner_never_starts_sync(tmp_path):
    from strattester.research.runner import ResearchRunner
    class Forbidden:
        def fetch_klines(self,*a,**k):pytest.fail('disabled strategy reached history client')
    store=SQLiteMarketStore.open(tmp_path/'m.db')
    try:
        d=StrategyDefinition('count','1',(DataRequirement('candles',('1m',)),),Count,enabled=False)
        with pytest.raises(ValueError,match='disabled'):
            ResearchRunner(store,Forbidden()).run(d,{'symbol':'X','launchTime':'0'},start_ms=0,end_ms=60000)
    finally:store.close()
