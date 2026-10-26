from pathlib import Path
from hashlib import sha256
import json
import runpy
import pytest


def prepare(tmp_path,**kwargs):
    tools=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))
    exe=tools['openssl_path']()
    from strattester.research.financial_test_package import prepare_test_package
    return prepare_test_package(tmp_path/'package',openssl_exe=exe,openssl_sha256=sha256(exe.read_bytes()).hexdigest(),scratch_root=tmp_path,seed=31,**kwargs)


def test_prepare_produces_signed_reproducible_offline_session_and_external_owner_template(tmp_path):
    p=prepare(tmp_path)
    config=Path(p['config_path']);assert sha256(config.read_bytes()).hexdigest()==p['config_sha256']
    assert Path(p['package_path']).is_file()
    build_script=config.parent/'source/scripts/build_windows_native.py'
    assert build_script.is_file()
    assert list((build_script.resolve().parents[1]/'native/windows').glob('*.cs'))
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_session import load_session,run_session
    tools=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))
    exe=tools['openssl_path']();verifier=OpenSSLVerifier(exe,sha256(exe.read_bytes()).hexdigest(),tmp_path)
    session=load_session(config,p['config_sha256'],trust_store_sha256=p['trust_store_sha256'],verifier=verifier)
    result=run_session(session,enable_research=True)
    assert result.get('physical_g1')=='NOT_AUTHORIZED' or result['provenance']['physical_g1']=='NOT_AUTHORIZED'
    template=json.loads((config.parent/'owner-plan-template.json').read_bytes())
    assert template['package_sha256'] is None
    assert 'owner' not in json.loads((config.parent/'trust.json').read_bytes())['keys'][0]['producer_id']


def test_prepare_refuses_existing_output_and_unknown_binary(tmp_path):
    prepare(tmp_path)
    with pytest.raises((ValueError,FileExistsError)):prepare(tmp_path)
    other=tmp_path/'other';other.mkdir();fake=other/'fake.exe';fake.write_bytes(b'not a reviewed binary')
    with pytest.raises(ValueError):prepare(other,native_binary=fake,native_binary_sha256='0'*64)
