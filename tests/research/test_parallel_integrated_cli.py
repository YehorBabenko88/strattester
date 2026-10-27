import hashlib
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mutation',['none','owner_secret','hash_mismatch','authorized'])
def test_preflight_cli_is_explicit_pinned_and_never_authorizes(tmp_path,capsys,mutation):
    from strattester.research_cli import main
    selection=json.loads((ROOT/'docs/readiness/TARGET_G0_SELECTION_STATUS.json').read_text())
    capture=json.loads((ROOT/'docs/readiness/TARGET_G0_PRIVATE_CAPTURE_PLAN.template.json').read_text())
    if mutation=='owner_secret':selection['vm_owner']='PRIVATE_OWNER_VALUE_DO_NOT_ECHO'
    if mutation=='authorized':capture['execution_authorized']=True
    args=['inspect-g0-preflight']
    for flag,value in [('selection',selection),('capture',capture)]:
        path=tmp_path/(flag+'.json');path.write_text(json.dumps(value))
        pin=hashlib.sha256(path.read_bytes()).hexdigest()
        if mutation=='hash_mismatch' and flag=='selection':pin='0'*64
        args+=['--'+flag,str(path),'--'+flag+'-sha256',pin]
    assert main(args)==2
    stdout=capsys.readouterr().out
    result=json.loads(stdout)
    assert result['status']=='BLOCKED' and result['physical_g1']=='NOT_AUTHORIZED'
    assert 'PRIVATE_OWNER_VALUE_DO_NOT_ECHO' not in stdout
    if mutation in ('none','owner_secret'):
        assert result['g0_qualification']=='BLOCKED' and result['missing_fields']
    else:assert result['code']=='RESEARCH_ERROR'
