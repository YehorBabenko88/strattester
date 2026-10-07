from strattester.research.learning_replay import LearningReplayEngine
from strattester.research.learning_event_log import LearningEventLog
from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.decision_memory import DecisionTrace,ObservedOutcome

def setup():
    o=ScientificOrganismController()
    log=LearningEventLog()
    for i in range(1,4):
        d=f"d{i}";o.remember_decision(DecisionTrace(d,i,"LONG",(),"R"))
        log.append(ObservedOutcome(d,"1h",1.0,i+10),{"m":1},regime="R")
    return o,log

def test_replay_applies_only_after_boundary():
    o,log=setup();o.last_applied_learning_sequence=1;o.applied_learning_events.add("d1:1h")
    r=LearningReplayEngine().replay(o,log.events())
    assert (r.applied,r.skipped,r.end_sequence)==(2,1,3)
    assert o.timescale_memory.state("m","R").regime_samples==2

def test_second_replay_is_noop():
    o,log=setup();engine=LearningReplayEngine()
    engine.replay(o,log.events());samples=o.timescale_memory.state("m","R").regime_samples
    r=engine.replay(o,log.events())
    assert r.applied==0 and r.skipped==3
    assert o.timescale_memory.state("m","R").regime_samples==samples

def test_missing_decision_trace_fails_before_advancing_boundary():
    o=ScientificOrganismController();log=LearningEventLog()
    log.append(ObservedOutcome("missing","1h",1,1),{"m":1},regime="R")
    try:LearningReplayEngine().replay(o,log.events())
    except ValueError as e:assert "missing decision trace" in str(e)
    else:raise AssertionError("orphan replay accepted")
    assert o.last_applied_learning_sequence==0


def test_late_orphan_event_does_not_partially_apply_earlier_events():
    o=ScientificOrganismController()
    o.remember_decision(DecisionTrace("good",1,"LONG",(),"R"))
    log=LearningEventLog()
    log.append(ObservedOutcome("good","1h",1,2),{"m":1},regime="R")
    log.append(ObservedOutcome("missing","1h",1,3),{"m":1},regime="R")
    try:LearningReplayEngine().replay(o,log.events())
    except ValueError as e:assert "missing decision trace" in str(e)
    else:raise AssertionError("orphan replay accepted")
    assert o.last_applied_learning_sequence==0
    assert o.timescale_memory.state("m","R").regime_samples==0
