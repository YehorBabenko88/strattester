from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor,ChannelLifecycle
from strattester.research.credit_assignment import CreditAssigner
from strattester.research.timescale_memory import MultiTimescaleMemory
from strattester.research.stability_landscape import BrainStabilityLandscape
from strattester.research.offline_consolidation import OfflineConsolidator

def parts():
    b=NeuroDecisionController();h=HomeostaticSupervisor(b);c=CreditAssigner(min_samples=2,z=0)
    m=MultiTimescaleMemory();l=BrainStabilityLandscape()
    return b,h,c,m,l

def test_active_channel_is_never_pruned():
    b,h,c,m,l=parts();b._channel("a").conductance=.3
    x=OfflineConsolidator(stale_cycles=1).run(b,h,c,m,l,active_channels=["a"],regime="R")
    assert "a" in x.protected and "a" not in x.pruned

def test_stale_weak_unconfirmed_channel_decays_but_has_floor():
    b,h,c,m,l=parts();b._channel("a").conductance=.4
    s=OfflineConsolidator(stale_cycles=1,prune_step=.2)
    s.run(b,h,c,m,l,active_channels=[],regime="R")
    assert b.channels["a"].conductance==.25

def test_quarantined_channel_can_be_pruned_immediately():
    b,h,c,m,l=parts();b._channel("q").conductance=1
    h._h("q").lifecycle=ChannelLifecycle.QUARANTINED
    x=OfflineConsolidator(stale_cycles=99).run(b,h,c,m,l,active_channels=[],regime="R")
    assert "q" in x.pruned and b.channels["q"].conductance<1

def test_native_update_requires_independent_validation():
    b,h,c,m,l=parts();b._channel("a")
    s=OfflineConsolidator(min_native_validation=.8,min_native_families=2)
    x=s.run(b,h,c,m,l,active_channels=["a"],regime="R",validation_score=.9,
            independent_families=1,allow_native_update=True)
    assert not x.native_updated and l.native is None
    x=s.run(b,h,c,m,l,active_channels=["a"],regime="R",validation_score=.9,
            independent_families=2,allow_native_update=True)
    assert x.native_updated and l.native is not None

def test_contradiction_blocks_new_native_state():
    from strattester.research.decision_memory import LearningSignal
    b,h,c,m,l=parts();b._channel("a")
    for _ in range(3):c.add("a",LearningSignal("d",1,None,None,0,True))
    for _ in range(4):m.add("a",-1,"R")
    x=OfflineConsolidator().run(b,h,c,m,l,active_channels=["a"],regime="R",
        validation_score=.99,independent_families=3,allow_native_update=True)
    assert "a" in x.contradictions and not x.native_updated
