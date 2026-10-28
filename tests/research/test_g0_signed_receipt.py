"""Real Ed25519 software fixtures; never physical identity or admission proof."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess

import pytest

from strattester.research.financial_snapshot import canonical_bytes


def fixture(root):
    from strattester.research.financial_g0_receipt import BINDING_FIELDS, DOMAIN
    helper = runpy.run_path(str(Path(__file__).with_name('test_financial_owner_authorization.py')))['fixture']
    keys = []; roles = []
    for name in ('owner', 'provider'):
        folder = root / name; folder.mkdir()
        _, args = helper(folder, owner_id=name, key_id=name)
        row = json.loads((folder / 'trust.json').read_text())['keys'][0]
        keys.append(row); roles.append((folder, args['verifier']))
    policy = dict(version=1, purpose='G0_BINDING_VERIFICATION_POLICY',
        expected={k: ('a'*40 if k in ('source_sha','tree_sha') else 'b'*64) for k in BINDING_FIELDS},
        owner_id='owner',provider_id='provider',owner_key_id='owner',provider_key_id='provider',
        valid_from_ns=100,valid_until_ns=200)
    manifest = dict(version=1,purpose='G0_READ_ONLY_BINDING_RECEIPT',binding=dict(policy['expected']),
        owner_id='owner',provider_id='provider',owner_key_id='owner',provider_key_id='provider',
        issued_at_ns=110,expires_at_ns=190,nonce='c'*64)
    trust = dict(version=1,keys=keys)
    def publish(signature_domain=DOMAIN):
        data = canonical_bytes(manifest)
        signatures = {}
        for role, (folder, verifier) in zip(('owner','provider'), roles):
            (folder/'g0-message').write_bytes(signature_domain+data)
            subprocess.run([str(verifier.executable),'pkeyutl','-sign','-rawin','-keyform','DER',
                '-inkey',str(folder/'test-key.der'),'-in',str(folder/'g0-message'),'-out',str(folder/'g0-signature')],
                capture_output=True,check=True,timeout=5)
            signatures[role] = base64.b64encode((folder/'g0-signature').read_bytes()).decode()
        for name, payload in [('receipt',dict(manifest,signatures=signatures)),('policy',policy),('trust',trust)]:
            (root/(name+'.json')).write_bytes(canonical_bytes(payload))
    publish()
    def verify(**changes):
        from strattester.research.financial_g0_receipt import verify_g0_receipt
        args={}
        for name in ('manifest','policy','trust_store'):
            file=root/({'manifest':'receipt','policy':'policy','trust_store':'trust'}[name]+'.json')
            args[name+'_path']=str(file);args[name+'_sha256']=sha256(file.read_bytes()).hexdigest()
        return verify_g0_receipt(**{**args,'verifier':roles[0][1],'now_ns':150,**changes})
    return manifest,policy,trust,publish,verify


def test_two_real_signatures_only_verify_binding_assertions(tmp_path):
    *_, verify = fixture(tmp_path)
    result = verify()
    assert result['signatures_verified'] is True
    assert result['status'] == 'BLOCKED'
    assert result['target_truth'] == 'NOT_ESTABLISHED_BY_SIGNATURE'
    assert result['physical_g1'] == 'NOT_AUTHORIZED'
    assert result['replay_protection'] == 'NOT_IMPLEMENTED_NO_ADMISSION'


@pytest.mark.parametrize('change', ['vm','source','sandbox','rollback','delivery','purpose',
    'expired','future','boolean_time','nonce','owner_alias','revoked','same_key'])
def test_even_resigned_incompatible_receipts_are_rejected(tmp_path, change):
    m,p,t,publish,verify=fixture(tmp_path)
    fields={'vm':'vm_identity_sha256','source':'source_sha','sandbox':'sandbox_root_sha256',
            'rollback':'rollback_receipt_sha256','delivery':'private_delivery_receipt_sha256'}
    if change in fields: m['binding'][fields[change]]='0'*len(m['binding'][fields[change]])
    elif change=='purpose': m['purpose']='PHYSICAL_G1_AUTHORIZATION'
    elif change=='expired': m['expires_at_ns']=140
    elif change=='future': m['issued_at_ns']=160
    elif change=='boolean_time': m['issued_at_ns']=True
    elif change=='nonce': m['nonce']=True
    elif change=='owner_alias': m['owner_id']='provider'
    elif change=='revoked': t['keys'][0]['revoked']=True
    elif change=='same_key': t['keys'][1]['public_key_b64']=t['keys'][0]['public_key_b64']
    publish()
    with pytest.raises(ValueError): verify()


def test_signature_substitution_rejected(tmp_path):
    *_, verify=fixture(tmp_path)
    path=tmp_path/'receipt.json'; payload=json.loads(path.read_text())
    payload['signatures']['owner']=base64.b64encode(bytes(64)).decode()
    path.write_bytes(canonical_bytes(payload))
    with pytest.raises(ValueError): verify()


def test_unfilled_policy_cannot_be_verified(tmp_path):
    m,p,t,publish,verify=fixture(tmp_path)
    p['expected']['vm_identity_sha256']=None
    publish()
    with pytest.raises(ValueError): verify()


@pytest.mark.parametrize('pin', ['manifest_sha256','policy_sha256','trust_store_sha256'])
def test_each_external_hash_pin_is_required(tmp_path, pin):
    *_, verify=fixture(tmp_path)
    with pytest.raises(ValueError, match='SHA256'): verify(**{pin:'0'*64})


def test_repeated_signature_check_never_claims_durable_replay_or_admission(tmp_path):
    *_, verify=fixture(tmp_path)
    for _ in range(2):
        result=verify()
        assert result['status']=='BLOCKED'
        assert result['replay_protection']=='NOT_IMPLEMENTED_NO_ADMISSION'


def test_public_fixture_key_alias_cannot_be_a_g0_authority(tmp_path):
    from strattester.research.financial_signatures import PUBLIC_SOFTWARE_FIXTURE_KEYS
    m,p,t,publish,verify=fixture(tmp_path)
    t['keys'][0]['public_key_b64']=base64.b64encode(next(iter(PUBLIC_SOFTWARE_FIXTURE_KEYS))).decode()
    publish()
    with pytest.raises(ValueError, match='public fixture'): verify()


def test_cli_verification_retains_blocked_exit_code(tmp_path, capsys):
    from strattester.research_cli import main
    fixture(tmp_path)
    verifier=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))['verifier'](tmp_path)
    args=['verify-g0-receipt','--verification-time-ns','150','--openssl-exe',str(verifier.executable),
          '--openssl-sha256',verifier.executable_sha256,'--scratch-root',str(tmp_path)]
    for flag,name in [('manifest','receipt'),('policy','policy'),('trust-store','trust')]:
        path=tmp_path/(name+'.json')
        args += ['--'+flag,str(path),'--'+flag+'-sha256',sha256(path.read_bytes()).hexdigest()]
    assert main(args)==2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='BLOCKED' and result['signatures_verified'] is True


@pytest.mark.parametrize('mutation',['provider_corrupt','swapped','bad_base64','extra_signature'])
def test_signature_set_attacks(tmp_path, mutation):
    *_,verify=fixture(tmp_path)
    path=tmp_path/'receipt.json';m=json.loads(path.read_text());s=m['signatures']
    if mutation=='provider_corrupt': s['provider']=base64.b64encode(bytes(64)).decode()
    elif mutation=='swapped': s['owner'],s['provider']=s['provider'],s['owner']
    elif mutation=='bad_base64': s['owner']='!not-base64!'
    else: s['other']=s['owner']
    path.write_bytes(canonical_bytes(m))
    with pytest.raises(ValueError): verify()


def test_other_signature_domain_rejected(tmp_path):
    m,p,t,publish,verify=fixture(tmp_path)
    publish(signature_domain=b'PHYSICAL_G1_AUTHORIZATION\x00')
    with pytest.raises(ValueError): verify()


@pytest.mark.parametrize('now,valid',[(110,True),(190,True),(109,False),(191,False)])
def test_receipt_time_boundaries(tmp_path, now, valid):
    *_,verify=fixture(tmp_path)
    if valid: assert verify(now_ns=now)['status']=='BLOCKED'
    else:
        with pytest.raises(ValueError): verify(now_ns=now)


@pytest.mark.parametrize('mutation',['over_24h','key_not_valid_at_issue','key_expired_now',
    'extra_manifest','extra_policy','boolean_policy_version','bad_role_type'])
def test_policy_schema_and_key_validity(tmp_path, mutation):
    m,p,t,publish,verify=fixture(tmp_path)
    if mutation=='over_24h': p['valid_until_ns']=p['valid_from_ns']+86400*1_000_000_000+1
    elif mutation=='key_not_valid_at_issue': t['keys'][1]['valid_from_ns']=120
    elif mutation=='key_expired_now': t['keys'][1]['valid_until_ns']=120
    elif mutation=='extra_manifest': m['extra']='untrusted'
    elif mutation=='extra_policy': p['extra']='untrusted'
    elif mutation=='boolean_policy_version': p['version']=True
    else: p['owner_id']=['owner']
    publish()
    with pytest.raises(ValueError): verify()


@pytest.mark.parametrize('value',[None,1,False])
def test_verifier_requires_literal_true(tmp_path, value):
    *_,verify=fixture(tmp_path)
    class NotAttested:
        def verify(self,*args): return value
    with pytest.raises(ValueError): verify(verifier=NotAttested())


def test_only_three_pinned_inputs_read_no_referenced_artifacts(tmp_path, monkeypatch):
    import socket
    import sqlite3
    from strattester.research import financial_g0_receipt as module, financial_signatures as signatures
    *_,verify=fixture(tmp_path)
    real=module.verified_bytes;calls=[]
    def read(path,*args):
        calls.append(Path(path).name)
        return real(path,*args)
    def forbidden(*args,**kwargs): raise AssertionError('unexpected external operation')
    monkeypatch.setattr(signatures.OpenSSLVerifier, 'verify', lambda self, *args: True)
    monkeypatch.setattr(module,'verified_bytes',read)
    monkeypatch.setattr(signatures,'verified_bytes',read)
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(socket,'socket',forbidden)
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    assert verify()['status']=='BLOCKED'
    assert calls==['policy.json','receipt.json','trust.json']


@pytest.mark.parametrize('name,limit',[('receipt',64*1024),('policy',32*1024),('trust',64*1024)])
def test_pinned_input_byte_budgets(tmp_path,name,limit):
    *_,verify=fixture(tmp_path)
    (tmp_path/(name+'.json')).write_bytes(b' '*(limit+1))
    with pytest.raises(ValueError,match='budget'): verify()
