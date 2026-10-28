"""Byte inventory of inert owned files; never launches an executable."""
from hashlib import sha256
import json
import subprocess
import pytest
from strattester.research.financial_snapshot import canonical_bytes


def fixture(tmp_path):
    file=tmp_path/'inert.exe';file.write_bytes(b'never executed')
    row=dict(logical_name='broker',absolute_path=str(file),sha256=sha256(file.read_bytes()).hexdigest(),size_bytes=file.stat().st_size)
    return dict(version=1,files=[row])


def publish(tmp_path,payload):
    data=canonical_bytes(payload);path=tmp_path/'inventory.json';path.write_bytes(data)
    return path,sha256(data).hexdigest()


def test_cli_inventory_verifies_bytes_without_execution_or_authorization(tmp_path,monkeypatch,capsys):
    from strattester.research_cli import main
    def deny(*a,**k):pytest.fail('inventory must not execute files')
    monkeypatch.setattr(subprocess,'run',deny)
    payload=fixture(tmp_path);path,pin=publish(tmp_path,payload)
    assert main(['verify-executables','--manifest',str(path),'--manifest-sha256',pin])==0
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='FILES_VERIFIED_ONLY'
    assert result['files'][0]['sha256']==payload['files'][0]['sha256']
    assert result['execution_binding']=='UNQUALIFIED'
    assert result['dependency_closure']=='NOT_PROVEN'
    assert result['physical_g1']=='NOT_AUTHORIZED'
    assert 'absolute_path' not in result['files'][0]


@pytest.mark.parametrize('change',[{'sha256':'0'*64},{'size_bytes':True},{'size_bytes':1},
    {'size_bytes':64*1024*1024+1},{'logical_name':'../escape'},{'absolute_path':'relative.exe'}])
def test_inventory_rejects_identity_or_budget_mismatch(tmp_path,change):
    from strattester.research.financial_executable_inventory import verify_executable_inventory
    payload=fixture(tmp_path);payload['files'][0].update(change);path,pin=publish(tmp_path,payload)
    with pytest.raises(ValueError):verify_executable_inventory(path,pin)


def test_duplicate_names_paths_and_manifest_pin_fail_closed(tmp_path):
    from strattester.research.financial_executable_inventory import verify_executable_inventory
    payload=fixture(tmp_path);payload['files']*=2;path,pin=publish(tmp_path,payload)
    with pytest.raises(ValueError):verify_executable_inventory(path,pin)
    payload['files'][1]={**payload['files'][0],'logical_name':'python'};path,pin=publish(tmp_path,payload)
    with pytest.raises(ValueError):verify_executable_inventory(path,pin)
    with pytest.raises(ValueError):verify_executable_inventory(path,'0'*64)


@pytest.mark.parametrize('target',['//server/share/tool.exe','\\\\server\\share\\tool.exe',
    '\\\\?\\C:\\tool.exe','/tmp/tool:stream','/tmp/invalid\x00.exe',
    r'\/server/share/tool.exe',r'/\server/share/tool.exe',
    'C:/NUL','C:/folder/CON.txt','C:/folder/COM1 .txt'])
def test_nonlocal_or_device_alias_is_rejected_before_target_io(tmp_path,monkeypatch,target):
    import strattester.research.financial_executable_inventory as inventory
    payload=fixture(tmp_path);payload['files'][0]['absolute_path']=target;path,pin=publish(tmp_path,payload)
    original=inventory.verified_bytes
    def read(file,*args):
        if str(file)!=str(path):raise AssertionError('target IO before local-path admission')
        return original(file,*args)
    monkeypatch.setattr(inventory,'verified_bytes',read)
    with pytest.raises(ValueError):inventory.verify_executable_inventory(path,pin)
