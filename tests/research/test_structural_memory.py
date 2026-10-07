from strattester.research.structural_memory import *

def test_absolute_noninvariant_values_do_not_change_class():
    a={"shape":"trend","vol_regime":"HIGH","price":100}
    b={"shape":"trend","vol_regime":"HIGH","price":100000}
    keys=["shape","vol_regime"]
    assert structural_signature(a,keys)==structural_signature(b,keys)

def test_invariant_feature_change_creates_new_class():
    a={"shape":"trend","vol_regime":"HIGH"}
    b={"shape":"mean_revert","vol_regime":"HIGH"}
    assert structural_signature(a,["shape","vol_regime"])!=structural_signature(b,["shape","vol_regime"])

def test_unfamiliar_structure_is_fail_closed():
    m=StructuralMemory(min_samples=3)
    ok,reasons=m.execution_permission("new")
    assert not ok and "structural_class_unfamiliar" in reasons

def test_repeated_reliable_structure_becomes_familiar():
    m=StructuralMemory(min_samples=3,min_confidence=.7)
    for i in range(3):m.observe(StructuralObservation("A","R",1,.9))
    e=m.experience("A")
    assert e.familiar and e.samples==3 and e.mean_utility==1
    assert m.execution_permission("A")[0]

def test_low_confidence_history_does_not_authorize_execution():
    m=StructuralMemory(min_samples=2,min_confidence=.8)
    for _ in range(5):m.observe(StructuralObservation("A","R",10,.2))
    assert not m.experience("A").familiar

def test_bad_familiar_structure_can_be_vetoed():
    m=StructuralMemory(min_samples=2)
    for _ in range(3):m.observe(StructuralObservation("A","R",-1,.9))
    ok,reasons=m.execution_permission("A",min_mean_utility=0)
    assert not ok and "structural_class_poor_history" in reasons

def test_transition_probabilities_are_empirical_and_directional():
    m=StructuralMemory(min_samples=1)
    for s in ["A","B","A","C","A","B"]:m.observe(StructuralObservation(s,"R",0,1))
    assert m.transition("A","B").count==2
    assert abs(m.transition("A","B").probability-2/3)<1e-9
    assert abs(m.transition("A","C").probability-1/3)<1e-9
