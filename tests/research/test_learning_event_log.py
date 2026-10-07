from strattester.research.learning_event_log import *
from strattester.research.decision_memory import ObservedOutcome

def test_duplicate_event_is_not_appended_twice():
    log=LearningEventLog();o=ObservedOutcome("d","1h",1.0,10)
    a,new1=log.append(o,{"m":1},regime="R")
    b,new2=log.append(o,{"m":1},regime="R")
    assert new1 and not new2 and a==b and len(log.events())==1

def test_conflicting_duplicate_fails_closed():
    log=LearningEventLog()
    log.append(ObservedOutcome("d","1h",1,10),{"m":1},regime="R")
    try:log.append(ObservedOutcome("d","1h",-1,11),{"m":1},regime="R")
    except ValueError as e:assert "collision" in str(e)
    else:raise AssertionError("conflicting outcome silently replaced")

def test_replay_order_is_deterministic():
    log=LearningEventLog()
    for i in range(3):log.append(ObservedOutcome(f"d{i}","1h",i,i),{"m":1},regime="R")
    assert [e.sequence for e in log.events()]==[1,2,3]
    assert [e.sequence for e in log.events(after_sequence=1)]==[2,3]

def test_event_id_is_stable_for_decision_horizon():
    a=learning_event_id(ObservedOutcome("d","1h",1,10))
    b=learning_event_id(ObservedOutcome("d","1h",-9,999))
    assert a==b
