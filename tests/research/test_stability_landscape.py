from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor,ChannelLifecycle
from strattester.research.stability_landscape import BrainStabilityLandscape,PlasticityGate

def controller():
    c=NeuroDecisionController()
    c._channel("a").conductance=1.0;c._channel("b").conductance=.8
    return c

def test_native_basin_tolerates_small_perturbation():
    c=controller();l=BrainStabilityLandscape(basin_radius=.3,min_energy_gap=.2)
    l.establish_native(c,.9);c.channels["a"].conductance=1.05
    r=l.assess(c,alternative_score=.2)
    assert r.in_basin and not r.recover

def test_competing_near_equal_state_is_metastable_and_not_healthy():
    c=controller();l=BrainStabilityLandscape(metastable_margin=.1)
    l.establish_native(c,.8)
    r=l.assess(c,alternative_score=.75)
    assert r.metastable and not r.in_basin

def test_large_drift_requests_chaperone_recovery():
    c=controller();l=BrainStabilityLandscape(recovery_radius=.4)
    l.establish_native(c,.9);c.channels["a"].conductance=2
    assert l.assess(c,alternative_score=.1).recover

def test_recovery_restores_known_channels_and_quarantines_unknown():
    c=controller();h=HomeostaticSupervisor(c);l=BrainStabilityLandscape()
    l.establish_native(c,.9)
    c.channels["a"].conductance=1.8;c._channel("rogue").conductance=2
    l.recover(c,h)
    assert c.channels["a"].conductance==1
    assert c.channels["rogue"].conductance<=.25
    assert h.health["rogue"].lifecycle==ChannelLifecycle.QUARANTINED

def test_native_state_requires_validation():
    c=controller();l=BrainStabilityLandscape()
    try:l.establish_native(c,0)
    except ValueError:pass
    else:raise AssertionError("unvalidated state became native")

def test_plasticity_requires_repeated_confirmation_and_bounds_change():
    c=controller();p=PlasticityGate(required_confirmations=3,max_step=.1)
    assert not p.consolidate(c,"a",1)
    assert not p.confirm("a",True);assert not p.confirm("a",True);assert p.confirm("a",True)
    assert p.consolidate(c,"a",1)
    assert abs(c.channels["a"].conductance-1.1)<1e-9

def test_failed_confirmation_delays_consolidation():
    p=PlasticityGate(required_confirmations=2)
    assert not p.confirm("x",True)
    assert not p.confirm("x",False)
    assert not p.confirm("x",True)
    assert p.confirm("x",True)
