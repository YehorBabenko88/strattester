import base64
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import runpy
import subprocess
import os
import pytest
from strattester.research.financial_snapshot import canonical_bytes


def fixture(tmp_path,*,public_fixture=False,**changes):
    from strattester.research.financial_owner_authorization import AUTHORIZATION_DOMAIN
    verifier=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))['verifier'](tmp_path)
    conf=tmp_path/'openssl.cnf';conf.write_bytes(b'')
    env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ};env['OPENSSL_CONF']=str(conf)
    def openssl(*arguments):
        return subprocess.run([str(verifier.executable),*map(str,arguments)],cwd=tmp_path,env=env,
                              stdin=subprocess.DEVNULL,check=True,capture_output=True,timeout=5)
    private=tmp_path/'test-key.der'
    if public_fixture:
        private.write_bytes(bytes.fromhex('302e020100300506032b6570042204204ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'))
    else:
        openssl('genpkey','-algorithm','ED25519','-outform','DER','-out',private)
    public=openssl('pkey','-inform','DER','-in',private,'-pubout','-outform','DER').stdout
    assert public[:12]==bytes.fromhex('302a300506032b6570032100') and len(public)==44
    p=dict(version=1,purpose='PHYSICAL_G1_AUTHORIZATION',owner_id='test-owner',key_id='ephemeral-owner',target_sha='a'*40,tree_sha='b'*40,binary_sha256='c'*64,package_sha256='d'*64,node_identity_sha256='e'*64,issued_at_ns=100,expires_at_ns=200,nonce='f'*64,operations=['synthetic_cpu_inference'],limits=dict(cpu_percent=10,memory_bytes=2147483648,wall_seconds=60,output_bytes=67108864,max_processes=1))
    p.update(changes);data=canonical_bytes(p);plan=tmp_path/'owner-plan.json';plan.write_bytes(data)
    trust=canonical_bytes(dict(version=1,keys=[dict(producer_id=p['owner_id'],key_id=p['key_id'],public_key_b64=base64.b64encode(public[12:]).decode(),valid_from_ns=0,valid_until_ns=1000,revoked=False)]))
    (tmp_path/'trust.json').write_bytes(trust)
    msg=tmp_path/'owner-message';msg.write_bytes(AUTHORIZATION_DOMAIN+data);sig=tmp_path/'owner-signature'
    openssl('pkeyutl','-sign','-rawin','-keyform','DER','-inkey',private,'-in',msg,'-out',sig)
    args=dict(plan_sha256=sha256(data).hexdigest(),signature_path=sig,signature_sha256=sha256(sig.read_bytes()).hexdigest(),trust_store_path=tmp_path/'trust.json',trust_store_sha256=sha256(trust).hexdigest(),owner_id=p['owner_id'],verifier=verifier,now_ns=150,expected_target_sha='a'*40,expected_tree_sha='b'*40,expected_binary_sha256='c'*64,expected_package_sha256='d'*64,expected_node_identity='e'*64)
    return plan,args


def test_valid_owner_signature_is_necessary_not_sufficient_for_g1(tmp_path):
    from strattester.research.financial_owner_authorization import verify_owner_authorization
    path,args=fixture(tmp_path);r=verify_owner_authorization(path,**args)
    assert r['authorization_signature_verified'] is True
    assert r['physical_g1']=='NOT_AUTHORIZED'
    assert r['native_enforcement']=='INDEPENDENT_PROOF_REQUIRED'

@pytest.mark.parametrize('change',[{'target_sha':'0'*40},{'tree_sha':'0'*40},{'binary_sha256':'0'*64},{'package_sha256':'0'*64},{'node_identity_sha256':'0'*64},{'expires_at_ns':120},{'issued_at_ns':160},{'operations':['trade']},{'purpose':'GRID_EXPORT'}])
def test_even_signed_incompatible_authorization_is_rejected(tmp_path,change):
    from strattester.research.financial_owner_authorization import verify_owner_authorization
    path,args=fixture(tmp_path,**change)
    with pytest.raises(ValueError):verify_owner_authorization(path,**args)


def test_owner_signature_substitution_is_denied(tmp_path):
    from strattester.research.financial_owner_authorization import verify_owner_authorization
    path,args=fixture(tmp_path);args['signature_path'].write_bytes(bytes(64));args['signature_sha256']=sha256(bytes(64)).hexdigest()
    with pytest.raises(ValueError):verify_owner_authorization(path,**args)


@pytest.mark.parametrize('owner,key',[('fixture-grid','rfc-key'),('claimed-owner','renamed-owner-key')])
def test_public_fixture_key_cannot_authorize_owner_even_under_alias(tmp_path,owner,key):
    from strattester.research.financial_owner_authorization import verify_owner_authorization
    path,args=fixture(tmp_path,public_fixture=True,owner_id=owner,key_id=key)
    with pytest.raises(ValueError,match='public fixture key'):
        verify_owner_authorization(path,**args)
