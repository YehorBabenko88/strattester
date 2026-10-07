from strattester.research.learning_event_log import *
from strattester.research.decision_memory import ObservedOutcome,CounterfactualEstimate

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


def test_export_restore_preserves_counterfactuals_and_sequence():
    log=LearningEventLog();o=ObservedOutcome("d","1h",1.5,10)
    cf=CounterfactualEstimate("d","1h","SHORT",-1,.7,"model",("frozen-oos",))
    log.append(o,{"m":.4},regime="R",counterfactuals=[cf])
    restored=LearningEventLog.restore(log.export())
    e=restored.events()[0]
    assert e.sequence==1 and e.counterfactuals==(cf,) and e.attribution==(("m",.4),)

def test_restore_rejects_tampered_event_identity():
    log=LearningEventLog();log.append(ObservedOutcome("d","1h",1,10),{"m":1},regime="R")
    p=log.export();p["events"][0]["event_id"]="tampered"
    try:LearningEventLog.restore(p)
    except ValueError as e:assert "id mismatch" in str(e)
    else:raise AssertionError("tampered event accepted")
