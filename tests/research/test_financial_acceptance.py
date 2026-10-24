from copy import deepcopy
import pytest
from strattester.research.financial_acceptance import validate_execution, aggregate


def report():
    return {'schema':1,'sha':'a'*40,'gate':'cpu','status':'PASS','passed':2,'failed':0,
            'errors':0,'skipped':0,'xfailed':0,'xpassed':0,'deselected':0,
            'collected':2,'nodeids':['file.py::test_a','file.py::test_b'], 'exit_code':0}


@pytest.mark.parametrize('change',[{'sha':'b'*40},{'skipped':1},{'failed':1},{'errors':1},
    {'xfailed':1},{'xpassed':1},{'deselected':1},{'collected':3},{'exit_code':2},
    {'nodeids':['file.py::test_a']},{'passed':True},{'status':'BLOCKED'}])
def test_incomplete_or_stale_execution_never_passes(change):
    r=report();r.update(change)
    with pytest.raises(ValueError):validate_execution(r,'a'*40,'cpu',{'file.py::test_a','file.py::test_b'},2)


def test_complete_execution_passes_but_external_blockers_prevent_acceptance():
    assert validate_execution(report(),'a'*40,'cpu',{'file.py::test_a','file.py::test_b'},2)
    r=aggregate({'cpu':report()},'a'*40,{'cpu'},external={'real_oos':'BLOCKED','gpu':'BLOCKED'})
    assert r['status']=='BLOCKED' and r['trading']=='NO-GO'


def test_missing_duplicate_or_wrong_gate_cannot_be_aggregated():
    assert aggregate({},'a'*40,{'cpu'},external={})['status']=='FAIL'
    bad=report();bad['gate']='data'
    assert aggregate({'cpu':bad},'a'*40,{'cpu'},external={})['status']=='FAIL'


def test_cancelled_job_cannot_pass_even_with_complete_test_artifact():
    assert aggregate({'cpu':report()},'a'*40,{'cpu'},external={},job_result='cancelled')['status']=='FAIL'
