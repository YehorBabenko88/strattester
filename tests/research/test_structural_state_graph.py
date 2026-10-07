from strattester.research.structural_state_graph import StructuralStateGraph

def test_graph_learns_directional_transitions():
    g=StructuralStateGraph(min_transition_samples=2,min_confidence=.5)
    for s in ["A","B","A","B","A","C"]:g.observe(s,regime="R")
    f=g.forecast("A")
    assert f.ranked[0][0]=="B"
    assert f.ranked[0][1]>f.ranked[1][1]

def test_unfamiliar_transition_graph_fails_closed():
    g=StructuralStateGraph(min_transition_samples=3)
    g.observe("A",regime="R");g.observe("B",regime="R")
    ok,reasons=g.execution_permission("A")
    assert not ok and "transition_graph_unfamiliar" in reasons

def test_prediction_requires_familiarity():
    g=StructuralStateGraph(min_transition_samples=2,min_confidence=.4)
    for s in ["A","B","A","B","A","B"]:g.observe(s,regime="R")
    assert g.predicted_targets("A")==("B",)

def test_novel_transition_is_maximally_surprising():
    g=StructuralStateGraph(min_transition_samples=1,min_confidence=0)
    for s in ["A","B","A","B"]:g.observe(s,regime="R")
    assert g.transition_surprise("A","C")==1.0
