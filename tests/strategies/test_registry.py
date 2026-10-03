import pytest
from strattester.strategies.base import StrategyDefinition,DataRequirement,strategy_fingerprint
from strattester.strategies.registry import StrategyRegistry
class S: pass
def d(version='1'): return StrategyDefinition('x',version,(DataRequirement('candles',('1m',)),),S)
def test_duplicate_rejected():
    r=StrategyRegistry(); r.register(d())
    with pytest.raises(ValueError): r.register(d())
def test_enable_disable_preserves_identity():
    r=StrategyRegistry(); r.register(d()); before=strategy_fingerprint(r.discover()[0])
    r.set_enabled('x','1',False); after=strategy_fingerprint(r.discover()[0])
    assert before==after and not r.discover()[0].enabled
def test_version_changes_result_identity():
    assert strategy_fingerprint(d('1')) != strategy_fingerprint(d('2'))


def test_builtin_registry_exposes_runnable_legacy_grid():
    from strattester.strategies.registry import builtin_registry
    found=builtin_registry().discover()
    assert [(x.id,x.version) for x in found]==[('legacy_grid','1.0')]
