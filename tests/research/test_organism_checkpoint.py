import json
import pytest
from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.homeostasis import ChannelLifecycle
from strattester.research.organism_checkpoint import save_checkpoint,load_checkpoint

def test_checkpoint_roundtrip_restores_adaptive_state(tmp_path):
    a=ScientificOrganismController();ch=a.brain._channel("m")
    ch.conductance=1.3;ch.adaptation=.4;ch.last_drive=.7;a.brain.potential=.2
    h=a.homeostasis._h("m");h.lifecycle=ChannelLifecycle.SENESCENT;h.successes=9
    a.plasticity_gate.pending["m"]=2
    a.applied_learning_events.update({"d1:1h","d2:4h"});a.last_applied_learning_sequence=17
    a.credit_assigner._scores["m"].extend([.2,.4])
    a.timescale_memory.add("m",.3,"R");a.timescale_memory.add("m",.5,"R")
    p=tmp_path/"brain.json";digest=save_checkpoint(a,p)
    b=ScientificOrganismController();assert load_checkpoint(b,p)==digest
    assert b.brain.channels["m"].conductance==1.3
    assert b.homeostasis.health["m"].lifecycle==ChannelLifecycle.SENESCENT
    assert b.homeostasis.health["m"].successes==9 and b.plasticity_gate.pending["m"]==2
    assert b.applied_learning_events=={"d1:1h","d2:4h"}
    assert b.last_applied_learning_sequence==17
    assert b.credit_assigner._scores["m"]==[.2,.4]
    assert b.timescale_memory.state("m","R").regime_samples==2

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
