from strattester.research.scientific_graph import ScientificArtifact
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor
from strattester.research.stability_landscape import BrainStabilityLandscape
from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
from strattester.research.organism_controller import ScientificOrganismController

def art(name,direction,strength=.5,confidence=.9,robustness=.9):
    return ScientificArtifact(name,"META",(),{"direction":direction,"strength":strength,"robustness":robustness},confidence)

def healthy_models():
    return [ModelIdentity("m1","trend","L1"),ModelIdentity("m2","vol","L2")]

def test_integrated_controller_can_act_when_all_gates_pass():
    brain=NeuroDecisionController(threshold=.4,leak=0)
    org=ScientificOrganismController(
        brain=brain,
        homeostasis=HomeostaticSupervisor(brain,clone_share_limit=.8),
        population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5))
    d=org.decide([art("a",1,.3),art("b",1,.3)],healthy_models(),external_permission=True)
    assert d.permitted and d.action=="LONG"
    assert not d.reasons

def test_unhealthy_model_population_blocks_execution():
    brain=NeuroDecisionController(threshold=.2,leak=0)
    org=ScientificOrganismController(
        brain=brain,
        homeostasis=HomeostaticSupervisor(brain,clone_share_limit=.9),
        population_guard=ModelPopulationGuard(max_lineage_share=.5))
    models=[ModelIdentity("a1","trend","A"),ModelIdentity("a2","trend","A",1,"a1")]
    d=org.decide([art("a",1,1)],models,external_permission=True)
    assert not d.permitted and d.action=="HOLD"
    assert "population_guard_block" in d.reasons

def test_metastable_landscape_vetoes_action():
    brain=NeuroDecisionController(threshold=.2,leak=0)
    landscape=BrainStabilityLandscape(metastable_margin=.1)
    org=ScientificOrganismController(
        brain=brain,
        homeostasis=HomeostaticSupervisor(brain,clone_share_limit=.8),
        landscape=landscape,
        population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5))
    org.establish_native(.8)
    d=org.decide([art("a",1,.5),art("b",1,.5)],healthy_models(),
                 external_permission=True,alternative_state_score=.75)
    assert d.action=="HOLD"
    assert "metastable_veto" in d.reasons

def test_learning_updates_health_and_is_bounded():
    brain=NeuroDecisionController()
    org=ScientificOrganismController(brain=brain,homeostasis=HomeostaticSupervisor(brain,max_conductance=1.2))
    for _ in range(20):org.learn_from_outcomes({"x":1},rate=1)
    assert brain.channels["x"].conductance==1.2
    assert org.homeostasis.health["x"].successes==20

def test_decision_history_is_bounded_by_query_not_storage():
    org=ScientificOrganismController()
    org.history=list(range(10))
    assert org.last_decisions(3)==(7,8,9)
