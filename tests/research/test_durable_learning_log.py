import hashlib,json
from strattester.research.durable_learning_log import *
from strattester.research.learning_event_log import LearningEvent
from strattester.research.decision_memory import CounterfactualEstimate

def _row(event):
    p=event_payload(event);raw=json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    return {"sequence":event.sequence,"event_id":event.event_id,"decision_id":event.decision_id,
            "horizon":event.horizon,"payload":p,"payload_hash":hashlib.sha256(raw.encode()).hexdigest()}

def test_decode_durable_event_preserves_counterfactual_provenance():
    cf=CounterfactualEstimate("d","1h","SHORT",-1,.8,"wf",("oos",))
    e=LearningEvent(4,"e","d","1h",2.0,100,"R",(("m",.5),),(cf,))
    assert decode_row(_row(e))==e

def test_corrupt_durable_payload_fails_before_replay():
    e=LearningEvent(1,"e","d","1h",2.0,100,"R",(),())
    row=_row(e);row["payload"]["utility"]=999
    try:decode_row(row)
    except ValueError as x:assert "hash mismatch" in str(x)
    else:raise AssertionError("corrupt durable event accepted")
