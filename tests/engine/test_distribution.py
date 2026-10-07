from strattester.engine.distribution import assign_node,assign_symbols,make_sync_jobs,make_backtest_jobs,reassign_unavailable
from strattester.engine.jobs import JobState

def test_assignment_is_deterministic():
    nodes=('PC1','PC2','PC3')
    a=assign_symbols(('BTCUSDT','ETHUSDT','SOLUSDT'),nodes)
    b=assign_symbols(('SOLUSDT','BTCUSDT','ETHUSDT'),reversed(nodes))
    assert a==b

def test_sync_and_backtest_follow_data_locality():
    nodes=('PC1','PC2','PC3')
    sync=make_sync_jobs(('BTCUSDT','ETHUSDT'),nodes)
    backtests=make_backtest_jobs(('BTCUSDT','ETHUSDT'),nodes,('A','B'))
    owner={j.symbol:j.target_node for j in sync}
    assert all(j.target_node==owner[j.symbol] for j in backtests)
    assert all(j.resource_key.startswith(f'market:{j.target_node}:') for j in sync)

def test_unavailable_node_can_be_reassigned():
    job=make_sync_jobs(('BTCUSDT',),('PC1',))[0]
    moved=reassign_unavailable(job,('PC2','PC3'))
    assert moved.target_node in ('PC2','PC3')
    assert moved.state is JobState.RETRYABLE
    assert moved.lease_owner is None
