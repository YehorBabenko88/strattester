from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor
from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
from strattester.research.brain_quorum import *
from strattester.research.scientific_graph import ScientificArtifact

def organism():
    b=NeuroDecisionController(threshold=.4,leak=0)
    return ScientificOrganismController(brain=b,
      homeostasis=HomeostaticSupervisor(b,clone_share_limit=.8),
      population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5))
def arts():
    return [ScientificArtifact(x,"META",(),{"direction":1,"strength":.6,"robustness":1},1) for x in ("x","y")]
def models():
    return [ModelIdentity("a","f1","l1"),ModelIdentity("b","f2","l2")]

def test_minority_partition_forces_hold():
    q=BrainQuorumFence(["n1","n2","n3"])
    qr=q.assess(PartitionView("n1",frozenset({"n1"}),2,10),BrainLease("n1",2,100))
    d=organism().decide(arts(),models(),external_permission=True,quorum_report=qr)
    assert not d.permitted and d.action=="HOLD"
    assert "quorum:no_majority_quorum" in d.reasons
    assert d.effective_uncertainty>=.25

def test_current_majority_lease_allows_normal_path():
    q=BrainQuorumFence(["n1","n2","n3"])
    qr=q.assess(PartitionView("n1",frozenset({"n1","n2"}),2,10),BrainLease("n1",2,100))
    d=organism().decide(arts(),models(),external_permission=True,quorum_report=qr)
    assert d.permitted and d.action=="LONG" and d.quorum.execution_allowed
