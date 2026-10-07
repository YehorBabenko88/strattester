from strattester.research.credit_assignment import CreditAssigner
from strattester.research.decision_memory import LearningSignal

def ls(v,regret=None,conf=0):
    return LearningSignal("d",v,None if regret is None else v+regret,regret,conf,True)

def test_single_lucky_outcome_cannot_rewire_brain():
    c=CreditAssigner(min_samples=5);c.add("m",ls(10))
    r=c.assess("m")
    assert r.verdict=="INSUFFICIENT" and r.modulation==0

def test_consistently_positive_oos_evidence_earns_credit():
    c=CreditAssigner(min_samples=5,max_modulation=.2)
    for x in [1,1.1,.9,1.2,1.05,1.1]:c.add("m",ls(x))
    r=c.assess("m")
    assert r.verdict=="BENEFICIAL" and 0<r.modulation<=.2

def test_consistently_negative_oos_evidence_loses_credit():
    c=CreditAssigner(min_samples=5,max_modulation=.2)
    for x in [-1,-1.1,-.9,-1.2,-1.05,-1.1]:c.add("m",ls(x))
    r=c.assess("m")
    assert r.verdict=="HARMFUL" and -.2<=r.modulation<0

def test_noisy_mixed_results_remain_uncertain():
    c=CreditAssigner(min_samples=6)
    for x in [-2,2,-1,1,-3,3,0]:c.add("m",ls(x))
    assert c.assess("m").verdict=="UNCERTAIN"

def test_counterfactual_regret_is_discounted_not_treated_as_fact():
    a=CreditAssigner(min_samples=2,z=0)
    b=CreditAssigner(min_samples=2,z=0)
    for _ in range(2):
        a.add("m",ls(1,regret=2,conf=.5))
        b.add("m",ls(1))
    assert a.assess("m").mean_score==.75
    assert b.assess("m").mean_score==1
