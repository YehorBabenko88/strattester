from copy import deepcopy
import json
from pathlib import Path
import pytest
from strattester.research.financial_acceptance import aggregate

SHA='a'*40
SPECS=json.loads((Path(__file__).resolve().parents[2]/'scripts/financial-gate-manifest.json').read_text())

def reports():
    return {g:dict(schema=1,sha=SHA,gate=g,status='PASS',passed=len(s['nodeids']),
        collected=len(s['nodeids']),nodeids=s['nodeids'],failed=0,errors=0,skipped=0,
        xfailed=0,xpassed=0,deselected=0,exit_code=0) for g,s in SPECS.items()}

@pytest.mark.parametrize('external',[{}, {'gpu':'PASS'},
    dict.fromkeys(('grid_coherent_snapshot','real_oos','gpu','full_upstream_equivalence'),'PASS')])
def test_external_claims_cannot_upgrade_missing_physical_evidence(external):
    result=aggregate(reports(),SHA,set(SPECS),external=external)
    assert result['status']!='PASS'
    assert result['trading']=='NO-GO'


def test_aggregator_uses_repository_manifest_not_report_self_description():
    rs=reports()
    rs['cpu'].update(nodeids=['forged.py::test_pass'],passed=1,collected=1)
    result=aggregate(rs,SHA,set(SPECS),external={'gpu':'BLOCKED'})
    assert result['status']=='FAIL'


def test_gate_set_cannot_be_reduced_to_one_forged_job():
    result=aggregate({'cpu':reports()['cpu']},SHA,{'cpu'},external={'gpu':'BLOCKED'})
    assert result['status']=='FAIL'


def test_boolean_schema_is_not_version_one():
    rs=reports();rs['cpu']['schema']=True
    assert aggregate(rs,SHA,set(SPECS),external={'gpu':'BLOCKED'})['status']=='FAIL'
