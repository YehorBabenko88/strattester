from strattester.runtime.commissioning import CommissioningManifest,CommissioningStage

def test_commissioning_is_strictly_ordered_and_durable(tmp_path):
    m=CommissioningManifest(tmp_path/'commissioning.json')
    assert m.next_stage() is CommissioningStage.INFRASTRUCTURE
    m.record(CommissioningStage.INFRASTRUCTURE,True,'2 nodes enrolled',now=1)
    assert m.next_stage() is CommissioningStage.NODE_CONNECTIVITY
    reopened=CommissioningManifest(tmp_path/'commissioning.json')
    assert reopened.next_stage() is CommissioningStage.NODE_CONNECTIVITY

def test_commissioning_cannot_skip_failed_or_missing_stage(tmp_path):
    import pytest
    m=CommissioningManifest(tmp_path/'commissioning.json')
    with pytest.raises(RuntimeError):
        m.record(CommissioningStage.DATABASE,True,'db ok')
    m.record(CommissioningStage.INFRASTRUCTURE,True,'ok')
    m.record(CommissioningStage.NODE_CONNECTIVITY,False,'PC2 unreachable')
    with pytest.raises(RuntimeError):
        m.record(CommissioningStage.CONTROL_PLANE,True,'must not run')

def test_production_ready_requires_every_prior_gate(tmp_path):
    import pytest
    m=CommissioningManifest(tmp_path/'commissioning.json')
    with pytest.raises(RuntimeError):
        m.record(CommissioningStage.PRODUCTION_READY,True,'unsafe')


def test_failed_recheck_invalidates_downstream_and_production_mode(tmp_path):
    m=CommissioningManifest(tmp_path/'commissioning.json')
    for stage in CommissioningStage:
        m.record(stage,True,'passed',now=1)
    assert m.load()['mode']=='PRODUCTION_READY'
    m.record(CommissioningStage.DATABASE,False,'connection lost',now=2)
    state=m.load()
    assert state['mode']=='COMMISSIONING'
    assert CommissioningStage.DATABASE.value not in state['completed']
    assert CommissioningStage.PRODUCTION_READY.value not in state['completed']
    assert m.next_stage() is CommissioningStage.DATABASE
    import pytest
    with pytest.raises(RuntimeError):
        m.record(CommissioningStage.PRODUCTION_READY,True,'unsafe',now=3)


def test_successful_recheck_preserves_completed_readiness(tmp_path):
    m=CommissioningManifest(tmp_path/'commissioning.json')
    for stage in CommissioningStage:
        m.record(stage,True,'passed',now=1)
    m.record(CommissioningStage.DATABASE,True,'rechecked',now=2)
    assert m.load()['mode']=='PRODUCTION_READY'
    assert m.next_stage() is None
