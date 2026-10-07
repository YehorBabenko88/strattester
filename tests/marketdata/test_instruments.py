from strattester.marketdata.instruments import InstrumentRegistry,InstrumentStatus

def test_new_symbol_is_ineligible_before_first_seen(tmp_path):
    r=InstrumentRegistry.open(tmp_path/'i.db')
    r.reconcile({'BTCUSDT'},1000)
    assert not r.eligible_at('BTCUSDT',999)
    assert r.eligible_at('BTCUSDT',1000)
    r.close()

def test_disappearance_retains_history_and_marks_delisted(tmp_path):
    r=InstrumentRegistry.open(tmp_path/'i.db')
    r.reconcile({'OLDUSDT'},1000)
    r.reconcile(set(),2000)
    assert r.get('OLDUSDT').status is InstrumentStatus.MISSING
    r.reconcile(set(),3000)
    x=r.get('OLDUSDT')
    assert x.status is InstrumentStatus.DELISTED
    assert x.first_seen==1000 and x.delisted_at==3000
    assert r.eligible_at('OLDUSDT',1500)
    assert not r.eligible_at('OLDUSDT',2000)
    r.close()

def test_suspension_can_resume_without_erasing_interval(tmp_path):
    r=InstrumentRegistry.open(tmp_path/'i.db')
    r.reconcile({'XUSDT'},1000)
    r.set_status('XUSDT',InstrumentStatus.SUSPENDED,1500)
    assert not r.eligible_at('XUSDT',1600)
    r.reconcile({'XUSDT'},2000)
    assert r.get('XUSDT').status is InstrumentStatus.ACTIVE
    assert r.eligible_at('XUSDT',2100)
    assert len(r.intervals('XUSDT'))==2
    r.close()

def test_delisted_state_survives_registry_reopen(tmp_path):
    path=tmp_path/'i.db'
    r=InstrumentRegistry.open(path)
    r.reconcile({'OLDUSDT'},1000)
    r.reconcile(set(),2000)
    r.close()

    reopened=InstrumentRegistry.open(path)
    assert reopened.get('OLDUSDT').status is InstrumentStatus.MISSING
    reopened.reconcile(set(),3000)
    assert reopened.get('OLDUSDT').status is InstrumentStatus.DELISTED
    assert reopened.intervals('OLDUSDT')==[(1000,2000)]
    assert reopened.eligible_at('OLDUSDT',1500)
    assert not reopened.eligible_at('OLDUSDT',2500)
    reopened.close()

def test_new_symbol_after_reopen_gets_fresh_active_interval(tmp_path):
    path=tmp_path/'i.db'
    r=InstrumentRegistry.open(path)
    r.reconcile({'BTCUSDT'},1000)
    r.close()

    reopened=InstrumentRegistry.open(path)
    reopened.reconcile({'BTCUSDT','NEWUSDT'},3000)
    assert reopened.get('NEWUSDT').status is InstrumentStatus.ACTIVE
    assert not reopened.eligible_at('NEWUSDT',2999)
    assert reopened.eligible_at('NEWUSDT',3000)
    reopened.close()


def test_transient_single_snapshot_absence_does_not_false_delist(tmp_path):
    r=InstrumentRegistry.open(tmp_path/'i.db')
    r.reconcile({'XUSDT'},1000);r.reconcile(set(),2000)
    assert r.get('XUSDT').status is InstrumentStatus.MISSING
    r.reconcile({'XUSDT'},3000)
    assert r.get('XUSDT').status is InstrumentStatus.ACTIVE
    assert r.intervals('XUSDT')==[(1000,2000),(3000,None)]

def test_missing_confirmation_survives_reboot_before_delist(tmp_path):
    p=tmp_path/'i.db';r=InstrumentRegistry.open(p)
    r.reconcile({'XUSDT'},1000);r.reconcile(set(),2000);r.close()
    r=InstrumentRegistry.open(p);r.reconcile(set(),3000)
    assert r.get('XUSDT').status is InstrumentStatus.DELISTED
    assert r.get('XUSDT').delisted_at==3000
