from strattester.research.decision_memory import *

def trace(i="d1",ctx="r1"):
    return DecisionTrace(i,1,"LONG",("confirmed",),ctx)

def test_observation_requires_real_decision():
    m=DecisionMemory()
    try:m.observe(ObservedOutcome("ghost","1h",1,2))
    except ValueError:pass
    else:raise AssertionError("orphan outcome accepted")

def test_counterfactual_requires_estimator_and_confidence():
    m=DecisionMemory();m.remember(trace())
    try:m.estimate(CounterfactualEstimate("d1","SHORT","1h",2,"",.9))
    except ValueError:pass
    else:raise AssertionError("anonymous estimate accepted")
    try:m.estimate(CounterfactualEstimate("d1","SHORT","1h",2,"wf",-1))
    except ValueError:pass
    else:raise AssertionError("invalid confidence accepted")

def test_low_confidence_counterfactual_cannot_create_regret():
    m=DecisionMemory();m.remember(trace());m.observe(ObservedOutcome("d1","1h",1,2))
    m.estimate(CounterfactualEstimate("d1","SHORT","1h",5,"walk_forward",.4))
    x=m.learning_signal("d1","1h",min_cf_confidence=.7)
    assert x.best_alternative is None and x.regret is None
    assert x.realized_utility==1

def test_reliable_counterfactual_reports_bounded_nonnegative_regret():
    m=DecisionMemory();m.remember(trace());m.observe(ObservedOutcome("d1","1h",1,2))
    m.estimate(CounterfactualEstimate("d1","HOLD","1h",.5,"replay",.9))
    m.estimate(CounterfactualEstimate("d1","SHORT","1h",2,"replay",.8))
    x=m.learning_signal("d1","1h")
    assert x.best_alternative==2 and x.regret==1 and x.counterfactual_confidence==.8

def test_better_realized_action_has_zero_regret():
    m=DecisionMemory();m.remember(trace());m.observe(ObservedOutcome("d1","1h",3,2))
    m.estimate(CounterfactualEstimate("d1","HOLD","1h",1,"replay",.9))
    assert m.learning_signal("d1","1h").regret==0

def test_context_history_does_not_mix_regimes():
    m=DecisionMemory();m.remember(trace("a","HIGH_VOL"));m.remember(trace("b","LOW_VOL"))
    assert [x.decision_id for x in m.comparable_history("HIGH_VOL")]==["a"]
