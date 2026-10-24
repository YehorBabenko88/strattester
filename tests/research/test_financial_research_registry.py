import runpy
from pathlib import Path
import pytest
from strattester.strategies.registry import StrategyRegistry
from strattester.engine.executor import execute_strategy


def test_explicit_registration_is_research_only_and_disabled():
    from strattester.strategies.builtin.financial_structural import register_financial_research
    registry=StrategyRegistry();assert registry.discover()==[]
    with pytest.raises(ValueError):register_financial_research(registry)
    definition=register_financial_research(registry,research_only=True)
    assert definition.enabled is False
    assert registry.discover()==[definition]
    with pytest.raises(ValueError):register_financial_research(registry,research_only=True)


def test_generic_mutable_store_executor_cannot_run_financial_backend():
    from strattester.strategies.builtin.financial_structural import register_financial_research
    registry=StrategyRegistry();d=register_financial_research(registry,research_only=True)
    with pytest.raises(ValueError,match='research context'):execute_strategy(d,object(),'BTCUSDT')


def test_research_registry_needs_explicit_enable_and_offline_context(tmp_path):
    from strattester.strategies.builtin.financial_structural import register_financial_research,execute_financial_research,FinancialResearchContext
    fixture=runpy.run_path(str(Path(__file__).with_name('test_financial_attested_inference.py')))
    b,r=fixture['setup'](tmp_path)
    registry=StrategyRegistry();d=register_financial_research(registry,research_only=True)
    context=FinancialResearchContext(r,b['policy'],b['verifier'])
    with pytest.raises(ValueError,match='disabled'):execute_financial_research(registry,context,research_only=True)
    registry.set_enabled(d.id,d.version,True)
    with pytest.raises(ValueError,match='research-only'):execute_financial_research(registry,context)
    result=execute_financial_research(registry,context,research_only=True)
    assert result.output['mode']=='OFFLINE_RESEARCH_ONLY'
    assert result.output['trades']==[]
    assert result.output['prediction']['instrument']['symbol']=='BTCUSDT'
    assert result.output['provenance']['checkpoint_sha256']==b['checkpoint_sha']
