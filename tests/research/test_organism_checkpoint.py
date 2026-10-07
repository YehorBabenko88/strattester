import json
import pytest
from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.homeostasis import ChannelLifecycle
from strattester.research.organism_checkpoint import save_checkpoint,load_checkpoint
from strattester.research.decision_memory import DecisionTrace,ObservedOutcome
from strattester.research.structural_memory import StructuralObservation

def test_checkpoint_roundtrip_restores_adaptive_state(tmp_path):
    a=ScientificOrganismController();ch=a.brain._channel("m")
    ch.conductance=1.3;ch.adaptation=.4;ch.last_drive=.7;a.brain.potential=.2
    h=a.homeostasis._h("m");h.lifecycle=ChannelLifecycle.SENESCENT;h.successes=9
    a.plasticity_gate.pending["m"]=2
    a.applied_learning_events.update({"d1:1h","d2:4h"});a.last_applied_learning_sequence=17
    a.credit_assigner._scores["m"].extend([.2,.4])
    a.timescale_memory.add("m",.3,"R");a.timescale_memory.add("m",.5,"R")
    a.remember_decision(DecisionTrace("decision-1",100,"LONG",("reason",),"ctx"))
    a.decision_memory.observe(ObservedOutcome("decision-1","1h",.7,200))
    a.structural_memory.observe_state("S1",sequence=10)
    a.structural_memory.observe_outcome(StructuralObservation("S1","R",.4,.9),outcome_id="so1")
    a.structural_state_graph.observe_state("S1",regime="R",sequence=10)
    a.structural_state_graph.observe_state("S2",regime="R",sequence=11)
    a.structural_state_graph.observe_outcome("S1",utility=.4,outcome_id="go1")
    p=tmp_path/"brain.json";digest=save_checkpoint(a,p)
    b=ScientificOrganismController();assert load_checkpoint(b,p)==digest
    assert b.brain.channels["m"].conductance==1.3
    assert b.homeostasis.health["m"].lifecycle==ChannelLifecycle.SENESCENT
    assert b.homeostasis.health["m"].successes==9 and b.plasticity_gate.pending["m"]==2
    assert b.applied_learning_events=={"d1:1h","d2:4h"}
    assert b.last_applied_learning_sequence==17
    assert b.credit_assigner._scores["m"]==[.2,.4]
    assert b.timescale_memory.state("m","R").regime_samples==2
    assert b.decision_memory.traces["decision-1"].context_fingerprint=="ctx"
    assert b.decision_memory.outcomes[("decision-1","1h")].utility==.7
    assert b.structural_memory.experience("S1").samples==1
    assert b.structural_memory._last_sequence==10
    assert b.structural_state_graph.forecast("S1").ranked[0][0]=="S2"
    assert b.structural_state_graph._last_sequence==11

def test_tampered_checkpoint_is_rejected_before_mutation(tmp_path):
    a=ScientificOrganismController();a.brain._channel("m").conductance=1.2
    p=tmp_path/"brain.json";save_checkpoint(a,p)
    x=json.loads(p.read_text());x["payload"]["brain"]["channels"]["m"]["conductance"]=1.9
    p.write_text(json.dumps(x))
    b=ScientificOrganismController();before=b.brain.potential
    with pytest.raises(ValueError,match="checksum"):load_checkpoint(b,p)
    assert b.brain.potential==before and "m" not in b.brain.channels

def test_unsafe_but_rechecksummed_state_is_rejected(tmp_path):
    import hashlib
    from strattester.research.organism_checkpoint import _canonical
    a=ScientificOrganismController();a.brain._channel("m");p=tmp_path/"brain.json";save_checkpoint(a,p)
    x=json.loads(p.read_text());x["payload"]["brain"]["channels"]["m"]["conductance"]=99
    x["sha256"]=hashlib.sha256(_canonical(x["payload"]).encode()).hexdigest();p.write_text(json.dumps(x))
    with pytest.raises(ValueError,match="unsafe conductance"):load_checkpoint(ScientificOrganismController(),p)


def test_late_decode_failure_leaves_live_organism_unchanged(tmp_path):
    import hashlib
    from strattester.research.organism_checkpoint import _canonical
    source=ScientificOrganismController();source.brain.potential=.8
    source.credit_assigner._scores["m"].append(.2)
    p=tmp_path/"brain.json";save_checkpoint(source,p)
    x=json.loads(p.read_text());x["payload"]["learning"]["credit_scores"]["m"]=[float("nan")]
    # json NaN is accepted by Python's parser; checksum is deliberately valid to test semantic validation.
    x["sha256"]=hashlib.sha256(_canonical(x["payload"]).encode()).hexdigest();p.write_text(json.dumps(x))
    live=ScientificOrganismController();live.brain.potential=.123
    with pytest.raises(ValueError,match="non-finite adaptive memory"):load_checkpoint(live,p)
    assert live.brain.potential==.123 and not live.credit_assigner._scores


def test_checkpoint_replace_failure_preserves_previous_checkpoint_and_cleans_tmp(tmp_path,monkeypatch):
    import os
    from strattester.research.organism_checkpoint import save_checkpoint
    org=_organism()
    path=tmp_path/'brain.json'
    first=save_checkpoint(org,path);before=path.read_bytes()
    real_replace=os.replace
    def fail(src,dst):raise OSError('simulated power-loss boundary')
    monkeypatch.setattr(os,'replace',fail)
    with pytest.raises(OSError):save_checkpoint(org,path)
    assert path.read_bytes()==before
    assert not (tmp_path/'brain.json.tmp').exists()
    monkeypatch.setattr(os,'replace',real_replace)
