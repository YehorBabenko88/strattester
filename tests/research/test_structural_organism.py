from strattester.research.organism_controller import ScientificOrganismController
from strattester.research.neuro_controller import NeuroDecisionController
from strattester.research.homeostasis import HomeostaticSupervisor
from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
from strattester.research.structural_memory import StructuralMemory,StructuralObservation
from strattester.research.structural_mathematics import StructuralReport
from strattester.research.scientific_graph import ScientificArtifact

def art(name,direction=1):
    return ScientificArtifact(name,"META",(),{"direction":direction,"strength":.5,"robustness":1},1)

def org():
    b=NeuroDecisionController(threshold=.4,leak=0)
    return ScientificOrganismController(
        brain=b,homeostasis=HomeostaticSupervisor(b,clone_share_limit=.8),
        population_guard=ModelPopulationGuard(min_diversity=.5,max_lineage_share=.6,max_mutation_rate=.5),
        structural_memory=StructuralMemory(min_samples=2,min_confidence=.7))

def models():
    return [ModelIdentity("m1","trend","L1"),ModelIdentity("m2","vol","L2")]

def test_novel_structural_class_is_researchable_but_fail_closed_when_required():
    o=org()
    d=o.decide([art("a"),art("b")],models(),external_permission=True,
               structural_signature="NEW",require_structural_familiarity=True)
    assert not d.permitted and d.action=="HOLD"
    assert "structural_class_unfamiliar" in d.reasons
    assert d.structural_experience.samples==0

def test_familiar_reliable_class_can_pass_memory_gate():
    o=org()
    for _ in range(2):o.structural_memory.observe(StructuralObservation("A","R",1,.9))
    d=o.decide([art("a"),art("b")],models(),external_permission=True,
               structural_signature="A",require_structural_familiarity=True)
    assert d.permitted and d.action=="LONG"
    assert d.structural_experience.familiar

def test_structural_health_and_memory_are_independent_gates():
    o=org()
    for _ in range(2):o.structural_memory.observe(StructuralObservation("A","R",1,.9))
    bad=StructuralReport(.1,1,1,1,False,("transformation_fragility",))
    d=o.decide([art("a"),art("b")],models(),external_permission=True,
               structural_signature="A",require_structural_familiarity=True,
               structural_report=bad)
    assert not d.permitted
    assert "structural:transformation_fragility" in d.reasons
