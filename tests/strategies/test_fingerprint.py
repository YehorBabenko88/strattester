from strattester.strategies.base import DataRequirement,StrategyDefinition,strategy_fingerprint
import strattester.strategies.base as base

class Impl:
    pass

def test_fingerprint_changes_when_implementation_source_changes(monkeypatch):
    d=StrategyDefinition('x','1',(DataRequirement('candles',('1m',)),),Impl)
    monkeypatch.setattr(base.inspect,'getsource',lambda _: 'return 1')
    a=strategy_fingerprint(d)
    monkeypatch.setattr(base.inspect,'getsource',lambda _: 'return 2')
    b=strategy_fingerprint(d)
    assert a!=b

def test_feature_definition_versions_affect_identity():
    a=StrategyDefinition('x','1',(DataRequirement('candles',('1m',)),),Impl,feature_versions=('smc-v1',))
    b=StrategyDefinition('x','1',(DataRequirement('candles',('1m',)),),Impl,feature_versions=('smc-v2',))
    assert strategy_fingerprint(a)!=strategy_fingerprint(b)
