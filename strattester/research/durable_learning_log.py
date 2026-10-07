"""Durable adapter between LearningEvent and the PostgreSQL append-only log."""
from __future__ import annotations
import hashlib,json,math
from .learning_event_log import LearningEvent
from .decision_memory import CounterfactualEstimate

def event_payload(event:LearningEvent):
    return {"utility":event.utility,"timestamp_ms":event.timestamp_ms,"regime":event.regime,
            "attribution":[list(x) for x in event.attribution],
            "counterfactuals":[{"decision_id":x.decision_id,"horizon":x.horizon,
              "alternative_action":x.alternative_action,"estimated_utility":x.estimated_utility,
              "confidence":x.confidence,"estimator":x.estimator,"assumptions":list(x.assumptions)}
              for x in event.counterfactuals]}

def _hash(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def decode_row(row):
    payload=row["payload"]
    if isinstance(payload,str):payload=json.loads(payload)
    if _hash(payload)!=str(row["payload_hash"]):raise ValueError("durable learning payload hash mismatch")
    utility=float(payload["utility"])
    if not math.isfinite(utility):raise ValueError("non-finite durable learning utility")
    attrs=tuple((str(k),float(v)) for k,v in payload.get("attribution",[]))
    if any(not math.isfinite(v) for _,v in attrs):raise ValueError("non-finite durable attribution")
    cfs=tuple(CounterfactualEstimate(**{**x,"assumptions":tuple(x.get("assumptions",()))})
              for x in payload.get("counterfactuals",[]))
    return LearningEvent(int(row["sequence"]),str(row["event_id"]),str(row["decision_id"]),
        str(row["horizon"]),utility,int(payload["timestamp_ms"]),str(payload["regime"]),attrs,cfs)

class DurableLearningLog:
    def __init__(self,state_store):self.state_store=state_store
    def append(self,event:LearningEvent,*,brain_holder=None,brain_epoch=None):
        return self.state_store.append_learning_log(event.event_id,event.decision_id,event.horizon,
            event_payload(event),brain_holder=brain_holder,brain_epoch=brain_epoch)
    def events(self,after_sequence=0,limit=1000):
        return tuple(decode_row(r) for r in self.state_store.learning_log_after(after_sequence,limit))
