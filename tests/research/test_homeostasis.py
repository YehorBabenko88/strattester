from strattester.research.neuro_controller import NeuroDecisionController,EvidenceSignal
from strattester.research.homeostasis import HomeostaticSupervisor,ChannelLifecycle

def s(k,d=1,strength=1,confidence=1,robustness=1):
    return EvidenceSignal(k,d,strength,confidence,robustness,1)

def test_external_permission_is_required_for_execution():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.2,leak=0))
    d=h.decide([s("a")],external_permission=False)
    assert d.permitted is False
    assert d.decision.action=="HOLD"
    assert "missing_external_permission" in d.vetoes

def test_repeated_autonomous_drive_becomes_senescent():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=99),autonomous_limit=2)
    for _ in range(4):
        h.decide([s("a")],external_permission=False)
    assert h.health["a"].lifecycle==ChannelLifecycle.SENESCENT

def test_low_reliability_strong_signal_is_quarantined():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=99),anomaly_quarantine=.7)
    d=h.decide([s("bad",1,1,.1,.1)],external_permission=True)
    assert "bad" in d.quarantined
    assert h.health["bad"].lifecycle==ChannelLifecycle.QUARANTINED

def test_repeated_failures_retire_model():
    h=HomeostaticSupervisor(NeuroDecisionController(),failure_retire=3)
    for _ in range(3):h.note_outcome("m",-1)
    assert h.health["m"].lifecycle==ChannelLifecycle.RETIRED

def test_mutation_budget_quarantines_unstable_model():
    h=HomeostaticSupervisor(NeuroDecisionController(),mutation_budget=2)
    h.note_model_change("m");h.note_model_change("m");h.note_model_change("m")
    assert h.health["m"].lifecycle==ChannelLifecycle.QUARANTINED

def test_clone_dominance_veto_blocks_single_model_capture():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.2,leak=0),clone_share_limit=.55)
    d=h.decide([s("dominant",1,1,1,1),s("weak",1,.1,1,1)],external_permission=True)
    assert d.permitted is False
    assert "clone_dominance" in d.vetoes

def test_independent_two_sieve_confirmation_can_execute():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.5,leak=0),clone_share_limit=.8)
    d=h.decide([s("a",1,.4),s("b",1,.4)],external_permission=True)
    assert d.permitted is True
    assert d.decision.action=="LONG"

def test_inhibitory_checkpoint_has_absolute_veto():
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.2,leak=0))
    d=h.decide([s("a")],external_permission=True,inhibitory_veto=True)
    assert d.permitted is False
    assert "inhibitory_checkpoint" in d.vetoes

def test_slow_modulation_cannot_run_away():
    h=HomeostaticSupervisor(NeuroDecisionController(),max_conductance=1.3)
    for _ in range(100):h.bounded_slow_modulate({"a":1},rate=1)
    assert h.controller.channels["a"].conductance==1.3

def test_unhealthy_structural_report_is_independent_veto():
    from strattester.research.structural_mathematics import StructuralReport
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.2,leak=0))
    structural=StructuralReport(.2,1,1,1,False,("transformation_fragility",))
    d=h.decide([s("a")],external_permission=True,structural_report=structural)
    assert d.permitted is False
    assert d.decision.action=="HOLD"
    assert "structural:transformation_fragility" in d.vetoes
    assert d.structural is structural

def test_healthy_structural_report_does_not_block_execution():
    from strattester.research.structural_mathematics import StructuralReport
    h=HomeostaticSupervisor(NeuroDecisionController(threshold=.5,leak=0),clone_share_limit=.8)
    structural=StructuralReport(1,1,1,1,True,())
    d=h.decide([s("a",1,.4),s("b",1,.4)],external_permission=True,
               structural_report=structural)
    assert d.permitted is True
    assert d.decision.action=="LONG"
