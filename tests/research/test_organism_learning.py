from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.credit_assignment import CreditAssigner
from strattester.research.timescale_memory import MultiTimescaleMemory
from strattester.research.stability_landscape import PlasticityGate
from strattester.research.decision_memory import DecisionTrace,ObservedOutcome

def make():
    return ScientificOrganismController(
        brain=NeuroDecisionController(),
        credit_assigner=CreditAssigner(min_samples=4,z=0,max_modulation=.1),
        timescale_memory=MultiTimescaleMemory(short_window=4,regime_window=8,long_window=32,
                                             short_decay=.5,regime_decay=.5,long_decay=.5),
        plasticity_gate=PlasticityGate(required_confirmations=2,max_step=.1))

def feed(org,i,utility,regime="R"):
    d=f"d{i}";org.remember_decision(DecisionTrace(d,i,"LONG",(),regime))
    return org.learn_decision(ObservedOutcome(d,"1h",utility,i+1),{"m":1},regime=regime)

def test_one_outcome_does_not_change_long_term_conductance():
    o=make();before=o.brain._channel("m").conductance
    feed(o,1,10)
    assert o.brain.channels["m"].conductance==before

def test_repeated_supported_outcomes_eventually_consolidate():
    o=make();before=o.brain._channel("m").conductance
    for i in range(20):feed(o,i,1)
    assert o.brain.channels["m"].conductance>before

def test_noisy_outcomes_do_not_consolidate():
    o=make();before=o.brain._channel("m").conductance
    for i,x in enumerate([1,-1]*10):feed(o,i,x)
    assert o.brain.channels["m"].conductance==before

def test_regime_memory_is_recorded_during_learning():
    o=make()
    for i in range(5):feed(o,i,1,"HIGH")
    assert o.timescale_memory.state("m","HIGH").regime_samples==5

def test_orphan_outcome_cannot_train_organism():
    o=make()
    try:o.learn_decision(ObservedOutcome("ghost","1h",1,1),{"m":1},regime="R")
    except ValueError:pass
    else:raise AssertionError("orphan outcome trained brain")
