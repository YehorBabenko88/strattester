from strattester.research.structural_mathematics import *

def test_invariance_detects_stable_signature_under_transformations():
    states=[1,2,3]
    assert transformation_invariance(lambda x:x%2,states,[lambda x:x+2])==1
    assert transformation_invariance(lambda x:x%2,states,[lambda x:x+1])==0

def test_balanced_design_rewards_equal_pair_exposure():
    balanced=[[1,2],[1,3],[2,3]]
    skewed=[[1,2],[1,2],[1,3]]
    assert balanced_pair_coverage(balanced)==1
    assert balanced_pair_coverage(skewed)<1

def test_temporal_tiling_penalizes_holes_and_overlap():
    req={"a","b","c"}
    assert temporal_tiling_score([["a"],["b"],["c"]],req)==1
    assert temporal_tiling_score([["a","b"],["b"]],req)<1

def test_periodic_word_has_less_complexity_than_richer_sequence():
    periodic=list("abababab")
    richer=list("abacabad")
    assert normalized_word_complexity(richer)>normalized_word_complexity(periodic)

def test_rational_approximation_is_bounded_and_interpretable():
    p,q,e=rational_approximation(0.33331,16)
    assert (p,q)==(1,3) and e<.001

def test_supervisor_fails_closed_on_structural_collapse():
    s=StructuralMathematicsSupervisor()
    r=s.assess(invariant_score=.9,balance_score=.2,coverage_score=1,complexity_score=.8)
    assert not r.healthy and "unbalanced_model_interactions" in r.reasons
