"""Deterministic checkpointing for scientific-organism adaptive state."""
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from pathlib import Path
from .homeostasis import ChannelLifecycle

SCHEMA_VERSION=3

def _canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def export_state(org):
    return {
      "schema_version":SCHEMA_VERSION,
      "brain":{"potential":org.brain.potential,
               "channels":{k:{"conductance":v.conductance,"adaptation":v.adaptation,"last_drive":v.last_drive}
                           for k,v in sorted(org.brain.channels.items())}},
      "health":{k:{"lifecycle":v.lifecycle.value,"age":v.age,"autonomous_drive":v.autonomous_drive,
                    "failures":v.failures,"successes":v.successes,"mutations":v.mutations,
                    "anomaly_score":v.anomaly_score} for k,v in sorted(org.homeostasis.health.items())},
      "plasticity":{"pending":dict(sorted(org.plasticity_gate.pending.items()))},
      "learning":{"applied_events":sorted(org.applied_learning_events),
                  "last_applied_sequence":int(org.last_applied_learning_sequence),
                  "credit_scores":{str(k):list(v) for k,v in sorted(org.credit_assigner._scores.items(),key=lambda x:str(x[0]))},
                  "short_memory":{str(k):list(v) for k,v in sorted(org.timescale_memory._short.items(),key=lambda x:str(x[0]))},
                  "regime_memory":[[str(k[0]),str(k[1]),list(v)] for k,v in sorted(org.timescale_memory._regime.items(),key=lambda x:str(x[0]))],
                  "long_memory":{str(k):list(v) for k,v in sorted(org.timescale_memory._long.items(),key=lambda x:str(x[0]))}},
    }

def save_checkpoint(org,path:Path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=export_state(org);raw=_canonical(payload)
    envelope={"payload":payload,"sha256":hashlib.sha256(raw.encode()).hexdigest()}
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(_canonical(envelope),encoding="utf-8");tmp.replace(path)
    return envelope["sha256"]

def load_checkpoint(org,path:Path):
    envelope=json.loads(Path(path).read_text(encoding="utf-8"))
    payload=envelope.get("payload");expected=envelope.get("sha256")
    if not isinstance(payload,dict) or not expected:raise ValueError("invalid brain checkpoint")
    actual=hashlib.sha256(_canonical(payload).encode()).hexdigest()
    if actual!=expected:raise ValueError("brain checkpoint checksum mismatch")
    if payload.get("schema_version")!=SCHEMA_VERSION:raise ValueError("unsupported brain checkpoint schema")
    # Validate fully before mutating live state.
    channels=payload.get("brain",{}).get("channels",{})
    for key,v in channels.items():
        if not .25<=float(v["conductance"])<=2.0:raise ValueError("unsafe conductance")
        if not 0<=float(v["adaptation"])<=1.0:raise ValueError("unsafe adaptation")
    for key,v in payload.get("health",{}).items():ChannelLifecycle(v["lifecycle"])
    org.brain.potential=float(payload["brain"]["potential"])
    for key,v in channels.items():
        ch=org.brain._channel(key);ch.conductance=float(v["conductance"])
        ch.adaptation=float(v["adaptation"]);ch.last_drive=float(v["last_drive"])
    for key,v in payload.get("health",{}).items():
        h=org.homeostasis._h(key);h.lifecycle=ChannelLifecycle(v["lifecycle"]);h.age=int(v["age"])
        h.autonomous_drive=int(v["autonomous_drive"]);h.failures=int(v["failures"])
        h.successes=int(v["successes"]);h.mutations=int(v["mutations"]);h.anomaly_score=float(v["anomaly_score"])
    org.plasticity_gate.pending={str(k):int(v) for k,v in payload.get("plasticity",{}).get("pending",{}).items()}
    learning=payload.get("learning",{})
    org.applied_learning_events=set(map(str,learning.get("applied_events",[])))
    org.last_applied_learning_sequence=int(learning.get("last_applied_sequence",0))
    org.credit_assigner._scores.clear()
    for k,v in learning.get("credit_scores",{}).items():org.credit_assigner._scores[str(k)].extend(map(float,v))
    org.timescale_memory._short.clear();org.timescale_memory._regime.clear();org.timescale_memory._long.clear()
    for k,v in learning.get("short_memory",{}).items():org.timescale_memory._short[str(k)].extend(map(float,v))
    for k,r,v in learning.get("regime_memory",[]):org.timescale_memory._regime[(str(k),str(r))].extend(map(float,v))
    for k,v in learning.get("long_memory",{}).items():org.timescale_memory._long[str(k)].extend(map(float,v))
    return actual
