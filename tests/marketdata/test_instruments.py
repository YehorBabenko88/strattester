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
    x=r.get('OLDUSDT')
    assert x.status is InstrumentStatus.DELISTED
    assert x.first_seen==1000 and x.delisted_at==2000
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
