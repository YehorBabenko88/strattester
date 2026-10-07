from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor
from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
from strattester.research.topology_recovery import ScientificTopologyRecovery
from strattester.research.adaptive_role_allocator import WorkerNode,RoleRequest
from strattester.research.scientific_graph import ScientificArtifact

def artifact(n):
    return ScientificArtifact(n,"META",(),{"direction":1,"strength":.6,"robustness":1},1)
def organism():
    b=NeuroDecisionController(threshold=.4,leak=0)
    return ScientificOrganismController(brain=b,
        homeostasis=HomeostaticSupervisor(b,clone_share_limit=.8),
        population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5))
def models():
    return [ModelIdentity("a","f1","l1"),ModelIdentity("b","f2","l2")]

def report(cycles=2,passes=1):
    r=ScientificTopologyRecovery(stabilization_cycles=cycles,stale_after_ms=100)
    ns=[WorkerNode("p1",frozenset({"risk"}),domain="1"),
        WorkerNode("p2",frozenset({"risk"}),domain="2")]
    for n in ns:r.heartbeat(n.node_id,0)
    x=None
    for i in range(passes):x=r.reconcile(ns,[RoleRequest("risk","risk",critical=True)],now_ms=i+1)
    return x

def test_recovering_topology_blocks_execution_and_is_explainable():
    o=organism();rr=report(cycles=2,passes=1)
    d=o.decide([artifact("x"),artifact("y")],models(),external_permission=True,recovery_report=rr)
    assert not d.permitted and d.action=="HOLD"
    assert any(x.startswith("recovery:topology_stabilizing") for x in d.reasons)
    assert d.recovery is rr

def test_healthy_recovered_topology_allows_normal_brain_path():
    o=organism();rr=report(cycles=2,passes=2)
    d=o.decide([artifact("x"),artifact("y")],models(),external_permission=True,recovery_report=rr)
    assert rr.execution_allowed and d.permitted and d.action=="LONG"

def test_recovery_uncertainty_is_added_to_brain_decision():
    o=organism();rr=report(cycles=2,passes=1)
    d=o.decide([artifact("x"),artifact("y")],models(),external_permission=True,
               uncertainty=.1,recovery_report=rr)
    assert d.effective_uncertainty>.1
    assert d.effective_uncertainty==min(1.0,.1+rr.uncertainty_addon)
