from strattester.research.neuro_controller import *

def sig(k,d,s=1,c=1,r=1,n=1):return EvidenceSignal(k,d,s,c,r,n)

def test_subthreshold_evidence_accumulates_then_fires():
    b=NeuroDecisionController(threshold=.6,leak=0,refractory_steps=2)
    assert b.integrate([sig("a",1,.25)]).action=="HOLD"
    assert b.integrate([sig("a",1,.25)]).action=="HOLD"
    assert b.integrate([sig("a",1,.25)]).action=="LONG"

def test_conflicting_channels_reduce_confidence_and_prevent_false_fire():
    b=NeuroDecisionController(threshold=.6,leak=0)
    d=b.integrate([sig("bull",1,.7),sig("bear",-1,.7)])
    assert d.action=="HOLD" and d.confidence==0
    assert d.excitation>0 and d.inhibition>0

def test_risk_and_uncertainty_raise_threshold():
    b=NeuroDecisionController(threshold=.5,leak=0)
    d=b.integrate([sig("a",1,.6)],risk=.5,uncertainty=.5)
    assert d.action=="HOLD" and d.threshold==1.0

def test_refractory_gate_blocks_immediate_repeat_decision():
    b=NeuroDecisionController(threshold=.4,leak=0,refractory_steps=2)
    assert b.integrate([sig("a",1,.5)]).action=="LONG"
    d=b.integrate([sig("a",1,1)])
    assert d.state==BrainState.REFRACTORY and d.action=="HOLD"

def test_sustained_signal_desensitizes_channel():
    b=NeuroDecisionController(threshold=99,leak=0,desensitize_at=.8)
    b.integrate([sig("a",1,1)])
    first=b.channels["a"].adaptation
    b.integrate([sig("a",1,1)])
    assert b.channels["a"].adaptation>first

def test_slow_feedback_is_bounded():
    b=NeuroDecisionController()
    for _ in range(100):b.slow_modulate({"a":1},rate=1)
    assert b.channels["a"].conductance==2.0
    for _ in range(100):b.slow_modulate({"a":-1},rate=1)
    assert b.channels["a"].conductance==.25

def test_only_explicit_signed_science_can_drive_brain():
    from strattester.research.scientific_graph import ScientificArtifact
    a=ScientificArtifact("regime","REGIME",(),{"regime":"HIGH"},.9)
    b=ScientificArtifact("edge","META",(),{"direction":1,"strength":.7,"robustness":.8},.9)
    xs=signals_from_artifacts([a,b])
    assert len(xs)==1 and xs[0].source_id==b.artifact_id
