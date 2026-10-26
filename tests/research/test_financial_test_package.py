from pathlib import Path
from hashlib import sha256
import json
import runpy
import subprocess
import sys
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
    assert template['version']==2
    assert template['input_hashes']['snapshot']==sha256((config.parent/'snapshot.json').read_bytes()).hexdigest()
    assert template['input_hashes']['package'] is None
    assert (config.parent/'runtime/strattester/research/financial_owner_intent_v2.py').is_file()
    assert (config.parent/'runtime/strattester/research/financial_funding.py').is_file()
    assert template['package_sha256'] is None
    assert 'owner' not in json.loads((config.parent/'trust.json').read_bytes())['keys'][0]['producer_id']
    # A fresh isolated interpreter must use packaged modules, not this checkout.
    code='''import sys,json,socket
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'runtime'))
def deny(*a,**k):raise AssertionError('offline network attempted')
socket.socket.connect=deny;socket.create_connection=deny
from strattester.research_cli import main
status=main(sys.argv[2:])
assert status==0
from strattester.research.financial_funding import FundingWindow,FundingEvent
from strattester.research.financial_evaluation import Trade,evaluate_ledger
funding=FundingWindow('fixture/linear/TEST',0,20,20,'a'*64,(FundingEvent('fixture/linear/TEST','event',10,11,'25','bps'),))
funded=evaluate_ledger([Trade(funding.instrument,0,20,0.,1)],funding_windows=(funding,))
assert funded['returns']==[-.0025]
assert funded['funding_status']=='RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED'
for name,module in list(sys.modules.items()):
 if (name=='strattester' or name.startswith('strattester.') or name.startswith('research.alphafold_training')) and getattr(module,'__file__',None):
  assert Path(module.__file__).is_relative_to(root/'runtime'),(name,module.__file__)
'''
    completed=subprocess.run([sys.executable,'-I','-c',code,str(config.parent),'run','--enable-research',
        '--config',str(config),'--config-sha256',p['config_sha256'],'--trust-store-sha256',p['trust_store_sha256'],
        '--openssl-exe',str(exe),'--openssl-sha256',sha256(exe.read_bytes()).hexdigest(),'--scratch-root',str(tmp_path)],
        cwd=config.parent,text=True,capture_output=True,timeout=60)
    assert completed.returncode==0,completed.stdout+completed.stderr
    experiment=config.parent/'experiment-input.json'
    assert experiment.is_file()
    completed=subprocess.run([sys.executable,'-I','-c',code,str(config.parent),'experiment','--enable-research',
        '--source',str(experiment),'--source-sha256',sha256(experiment.read_bytes()).hexdigest(),
        '--output',str(tmp_path/'experiment-result')],cwd=config.parent,text=True,capture_output=True,timeout=60)
    assert completed.returncode==0,completed.stdout+completed.stderr


def test_prepare_refuses_existing_output_and_unknown_binary(tmp_path):
    prepare(tmp_path)
    with pytest.raises((ValueError,FileExistsError)):prepare(tmp_path)
    other=tmp_path/'other';other.mkdir();fake=other/'fake.exe';fake.write_bytes(b'not a reviewed binary')
    with pytest.raises(ValueError):prepare(other,native_binary=fake,native_binary_sha256='0'*64)
