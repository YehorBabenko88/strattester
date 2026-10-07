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


def test_same_outcome_retry_is_applied_only_once():
    o=make();o.remember_decision(DecisionTrace("same",1,"LONG",(),"R"))
    out=ObservedOutcome("same","1h",1,2)
    o.learn_decision(out,{"m":1},regime="R")
    samples=o.timescale_memory.state("m","R").regime_samples
    assert o.learn_decision(out,{"m":1},regime="R")=={}
    assert o.timescale_memory.state("m","R").regime_samples==samples
    assert "same:1h" in o.applied_learning_events

class RejectDuplicateStore:
    def __init__(self):self.claims=set()
    def claim_learning_event(self,event_id,decision_id,horizon,meta=None):
        k=(decision_id,horizon)
        if k in self.claims:return False
        self.claims.add(k);return True

def test_durable_store_blocks_duplicate_across_controller_restart():
    store=RejectDuplicateStore()
    a=make();a.remember_decision(DecisionTrace("d",1,"LONG",(),"R"))
    a.learn_decision(ObservedOutcome("d","1h",1,2),{"m":1},regime="R",learning_store=store)
    b=make();b.remember_decision(DecisionTrace("d",1,"LONG",(),"R"))
    assert b.learn_decision(ObservedOutcome("d","1h",1,2),{"m":1},regime="R",learning_store=store)=={}
    assert b.timescale_memory.state("m","R").regime_samples==0
