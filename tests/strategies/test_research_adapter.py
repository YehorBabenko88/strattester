from strattester.strategies.registry import builtin_registry

def test_builtin_registry_exposes_research_families():
    ids={x.id for x in builtin_registry().discover()}
    expected={'legacy_grid','level_base','smc_ob','poc_mean_reversion','vol_compression_expansion','orderflow_absorption_proxy'}
    assert expected.issubset(ids)

def test_research_requirements_are_explicit():
    items={x.id:x for x in builtin_registry().discover()}
    flow={r.dataset.value for r in items['orderflow_absorption_proxy'].requirements}
    oi={r.dataset.value for r in items['level_oi'].requirements}
    assert 'public_trade_aggregates' in flow
    assert 'open_interest' in oi
