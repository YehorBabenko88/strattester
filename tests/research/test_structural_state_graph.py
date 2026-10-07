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


def test_delayed_graph_outcome_cannot_rewrite_transition_order():
    g=StructuralStateGraph(min_transition_samples=1,min_confidence=0)
    g.observe_state("A",regime="R",sequence=1);g.observe_state("B",regime="R",sequence=2)
    g.observe_outcome("A",utility=5,outcome_id="late")
    assert g.forecast("A").ranked[0][0]=="B"
    assert not g.forecast("B").ranked

def test_graph_rejects_out_of_order_state_sequence():
    g=StructuralStateGraph();g.observe_state("A",regime="R",sequence=10)
    try:g.observe_state("B",regime="R",sequence=9)
    except ValueError as e:assert "non-monotonic" in str(e)
    else:raise AssertionError("out-of-order state accepted")


def test_one_deterministic_transition_is_not_high_confidence():
    g=StructuralStateGraph(min_transition_samples=5,min_confidence=.65)
    g.observe("A",regime="R");g.observe("B",regime="R")
    f=g.forecast("A")
    assert f.samples==1 and f.confidence<.5 and not f.familiar

def test_confidence_requires_repeated_transition_evidence():
    g=StructuralStateGraph(min_transition_samples=5,min_confidence=.45)
    for s in ["A","B","A","B","A","B","A","B","A","B","A","B"]:g.observe(s,regime="R")
    f=g.forecast("A")
    assert f.samples>=5 and f.confidence>=.45 and f.familiar

def test_invalid_prior_strength_fails_closed():
    try:StructuralStateGraph(prior_strength=0)
    except ValueError:pass
    else:raise AssertionError("invalid prior accepted")
