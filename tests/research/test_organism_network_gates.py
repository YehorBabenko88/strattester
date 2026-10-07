from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor
from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
from strattester.research.structural_state_graph import StructuralStateGraph
from strattester.research.agent_communication import SelfOrganizingCommunicationFabric
from strattester.research.scientific_graph import ScientificArtifact

def art(n):
    return ScientificArtifact(n,"META",(),{"direction":1,"strength":.6,"robustness":1},1)
def models():
    return [ModelIdentity("a","f1","l1"),ModelIdentity("b","f2","l2")]
def make(graph=None,fabric=None):
    b=NeuroDecisionController(threshold=.4,leak=0)
    return ScientificOrganismController(
        brain=b,homeostasis=HomeostaticSupervisor(b,clone_share_limit=.8),
        population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5),
        structural_state_graph=graph,communication_fabric=fabric)

def test_unfamiliar_transition_can_fail_closed():
    o=make()
    d=o.decide([art("x"),art("y")],models(),external_permission=True,
               structural_signature="A",require_transition_familiarity=True)
    assert not d.permitted and d.action=="HOLD"
    assert "transition_graph_unfamiliar" in d.reasons

def test_familiar_transition_passes_transition_gate():
    g=StructuralStateGraph(min_transition_samples=2,min_confidence=.3)
    for s in ["A","B","A","B","A","B"]:g.observe(s,regime="R")
    o=make(graph=g)
    d=o.decide([art("x"),art("y")],models(),external_permission=True,
               structural_signature="A",require_transition_familiarity=True)
    assert d.permitted and d.transition_forecast.familiar

def test_unhealthy_communication_topology_vetoes_execution():
    f=SelfOrganizingCommunicationFabric()
    f.link("a","brain").weight=2
    f.link("b","brain").weight=.15
    o=make(fabric=f)
    d=o.decide([art("x"),art("y")],models(),external_permission=True)
    assert not d.permitted and "communication_topology_unhealthy" in d.reasons
    assert not d.communication_health["healthy"]

def test_communication_gate_can_be_disabled_for_offline_research():
    f=SelfOrganizingCommunicationFabric()
    f.link("a","brain").weight=2;f.link("b","brain").weight=.15
    o=make(fabric=f)
    d=o.decide([art("x"),art("y")],models(),external_permission=True,
               require_communication_health=False)
    assert d.permitted
