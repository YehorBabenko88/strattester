from strattester.research.population_guard import ModelIdentity,ModelPopulationGuard
def m(i,f,l,g=0,p=None):return ModelIdentity(i,f,l,g,p)

def test_clones_cannot_manufacture_consensus():
    g=ModelPopulationGuard(max_lineage_share=.6)
    ms=[m("a1","trend","A"),m("a2","trend","A",1,"a1"),m("a3","trend","A",2,"a2"),m("b","vol","B")]
    r=g.assess(ms)
    assert not r.healthy and "clonal_expansion" in r.reasons
    w=g.consensus_weights(ms)
    assert abs(sum(w[x] for x in ("a1","a2","a3"))-.5)<1e-9
    assert abs(w["b"]-.5)<1e-9

def test_related_models_are_not_independent_validators():
    c=m("child","trend","A",1,"parent")
    vals=[m("sib","trend","A"),m("otherfam","vol","B"),m("samefam","trend","C")]
    independent=ModelPopulationGuard.independent_confirmation(c,vals)
    assert [x.model_id for x in independent]==["otherfam"]

def test_healthy_population_requires_independent_families():
    g=ModelPopulationGuard(min_diversity=.4,max_lineage_share=.6,max_mutation_rate=.5)
    r=g.assess([m("a","trend","A"),m("b","vol","B"),m("c","state","C")])
    assert r.healthy

def test_mutation_burst_is_detected():
    g=ModelPopulationGuard(max_mutation_rate=.25)
    r=g.assess([m("a","x","A",1),m("b","y","B",1),m("c","z","C"),m("d","q","D")])
    assert not r.healthy and "excess_mutation_rate" in r.reasons
