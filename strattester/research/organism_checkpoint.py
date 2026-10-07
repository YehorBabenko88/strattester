"""Deterministic checkpointing for scientific-organism adaptive state."""
from __future__ import annotations
import hashlib,json,math,copy
from dataclasses import dataclass
from pathlib import Path
from .homeostasis import ChannelLifecycle
from .decision_memory import DecisionTrace,ObservedOutcome,CounterfactualEstimate
from .structural_memory import StructuralObservation

SCHEMA_VERSION=4

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
      "decision_memory":{
        "traces":[vars(v) for _,v in sorted(org.decision_memory.traces.items())],
        "outcomes":[vars(v) for _,v in sorted(org.decision_memory.outcomes.items())],
        "counterfactuals":[vars(v) for _,v in sorted(org.decision_memory.counterfactuals.items())]},
      "structural_memory":{
        "observations":[vars(o) for sig in sorted(org.structural_memory._obs) for o in org.structural_memory._obs[sig]],
        "transitions":[[a,b,n] for (a,b),n in sorted(org.structural_memory._transitions.items())],
        "last":org.structural_memory._last,"last_sequence":org.structural_memory._last_sequence,
        "outcome_ids":sorted(org.structural_memory._outcome_ids)},
      "structural_graph":{
        "visits":dict(sorted(org.structural_state_graph._visits.items())),
        "utility":{k:list(v) for k,v in sorted(org.structural_state_graph._utility.items())},
        "regimes":{k:sorted(v) for k,v in sorted(org.structural_state_graph._regimes.items())},
        "edges":[[a,b,n] for (a,b),n in sorted(org.structural_state_graph._edges.items())],
        "last":org.structural_state_graph._last,"last_sequence":org.structural_state_graph._last_sequence,
        "outcome_ids":sorted(org.structural_state_graph._outcome_ids)},
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

def _validate_payload(payload):
    if payload.get("schema_version")!=SCHEMA_VERSION:raise ValueError("unsupported brain checkpoint schema")
    brain=payload.get("brain",{});potential=float(brain["potential"])
    if not math.isfinite(potential):raise ValueError("non-finite brain potential")
    for v in brain.get("channels",{}).values():
        vals=(float(v["conductance"]),float(v["adaptation"]),float(v["last_drive"]))
        if not all(math.isfinite(x) for x in vals):raise ValueError("non-finite channel state")
        if not .25<=vals[0]<=2.0:raise ValueError("unsafe conductance")
        if not 0<=vals[1]<=1.0:raise ValueError("unsafe adaptation")
    for v in payload.get("health",{}).values():
        ChannelLifecycle(v["lifecycle"])
        if any(int(v[k])<0 for k in ("age","autonomous_drive","failures","successes","mutations")):
            raise ValueError("negative health counter")
        if not math.isfinite(float(v["anomaly_score"])):raise ValueError("non-finite anomaly score")
    learning=payload.get("learning",{})
    if int(learning.get("last_applied_sequence",0))<0:raise ValueError("negative learning boundary")
    for section in ("credit_scores","short_memory","long_memory"):
        for values in learning.get(section,{}).values():
            if any(not math.isfinite(float(x)) for x in values):raise ValueError("non-finite adaptive memory")
    return True

def load_checkpoint(org,path:Path):
    load_checkpoint._live_target=org
    envelope=json.loads(Path(path).read_text(encoding="utf-8"))
    payload=envelope.get("payload");expected=envelope.get("sha256")
    if not isinstance(payload,dict) or not expected:raise ValueError("invalid brain checkpoint")
    actual=hashlib.sha256(_canonical(payload).encode()).hexdigest()
    if actual!=expected:raise ValueError("brain checkpoint checksum mismatch")
    _validate_payload(payload)
    # Apply to a deep copy first: malformed nested provenance can never leave
    # the live organism half-restored.
    target=copy.deepcopy(org)
    channels=payload.get("brain",{}).get("channels",{})
    org=target
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
    dm=payload.get("decision_memory",{})
    org.decision_memory.traces={x["decision_id"]:DecisionTrace(**{**x,"reasons":tuple(x["reasons"])}) for x in dm.get("traces",[])}
    org.decision_memory.outcomes={(x["decision_id"],x["horizon"]):ObservedOutcome(**x) for x in dm.get("outcomes",[])}
    org.decision_memory.counterfactuals={(x["decision_id"],x["horizon"],x["alternative_action"]):
        CounterfactualEstimate(**{**x,"assumptions":tuple(x.get("assumptions",()))}) for x in dm.get("counterfactuals",[])}
    sm=payload.get("structural_memory",{});org.structural_memory._obs.clear()
    for x in sm.get("observations",[]):org.structural_memory._obs[x["signature"]].append(StructuralObservation(**x))
    org.structural_memory._transitions.clear()
    for a,b,n in sm.get("transitions",[]):org.structural_memory._transitions[(a,b)]=int(n)
    org.structural_memory._last=sm.get("last");org.structural_memory._last_sequence=sm.get("last_sequence")
    org.structural_memory._outcome_ids=set(map(str,sm.get("outcome_ids",[])))
    sg=payload.get("structural_graph",{});g=org.structural_state_graph
    g._visits.clear();g._visits.update({str(k):int(v) for k,v in sg.get("visits",{}).items()})
    g._utility.clear()
    for k,v in sg.get("utility",{}).items():g._utility[str(k)].extend(map(float,v))
    g._regimes.clear()
    for k,v in sg.get("regimes",{}).items():g._regimes[str(k)].update(map(str,v))
    g._edges.clear()
    for a,b,n in sg.get("edges",[]):g._edges[(a,b)]=int(n)
    g._last=sg.get("last");g._last_sequence=sg.get("last_sequence");g._outcome_ids=set(map(str,sg.get("outcome_ids",[])))
    org.applied_learning_events=set(map(str,learning.get("applied_events",[])))
    org.last_applied_learning_sequence=int(learning.get("last_applied_sequence",0))
    org.credit_assigner._scores.clear()
    for k,v in learning.get("credit_scores",{}).items():org.credit_assigner._scores[str(k)].extend(map(float,v))
    org.timescale_memory._short.clear();org.timescale_memory._regime.clear();org.timescale_memory._long.clear()
    for k,v in learning.get("short_memory",{}).items():org.timescale_memory._short[str(k)].extend(map(float,v))
    for k,r,v in learning.get("regime_memory",[]):org.timescale_memory._regime[(str(k),str(r))].extend(map(float,v))
    for k,v in learning.get("long_memory",{}).items():org.timescale_memory._long[str(k)].extend(map(float,v))
    original=locals().get('target')
    # Commit the fully decoded state only after every reconstruction succeeded.
    live=load_checkpoint._live_target
    live.__dict__.clear();live.__dict__.update(org.__dict__)
    return actual
