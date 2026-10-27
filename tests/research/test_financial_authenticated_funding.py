"""Genuine public-key signatures; synthetic cashflows only, not producer history."""
import base64
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest


def bundle(root):
    from strattester.research.financial_authenticated_funding import FundingPolicy, FUNDING_DOMAIN, FUNDING_SCHEMA_SHA256
    from strattester.research.financial_contract import Instrument
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_snapshot import canonical_bytes
    keys = runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))
    exe = Path(shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe').resolve()
    assert exe.is_file()
    verifier = OpenSSLVerifier(exe, sha256(exe.read_bytes()).hexdigest(), root)
    trust = dict(version=1, keys=[dict(producer_id='fixture-funding', key_id='rfc-key',
        public_key_b64=base64.b64encode(keys['PUBLIC']).decode(), valid_from_ns=0,
        valid_until_ns=1000, revoked=False)])
    data = canonical_bytes(trust)
    (root/'trust.json').write_bytes(data)
    policy = FundingPolicy('fixture-funding', 'a'*40, 'fixture-source', 'b'*64,
        'cut-1', 'epoch-1', Instrument('venue', 'perpetual', 'SOL'), 10, 0, 100, 100, 110)
    manifest = dict(version=1, schema_sha256=FUNDING_SCHEMA_SHA256, producer_id=policy.producer_id,
        producer_build_sha=policy.producer_build_sha, key_id='rfc-key', source_id=policy.source_id,
        source_schema_sha256=policy.source_schema_sha256, snapshot_id=policy.snapshot_id,
        coherence_epoch_id=policy.coherence_epoch_id, knowledge_cutoff_ns=100, issued_at_ns=101,
        scope='SYNTHETIC_ENGINEERING_ONLY', partition=dict(exchange='venue',market_type='perpetual',symbol='SOL',timeframe_ns=10),
        start_ns=0, end_ns=100, complete=True, first_availability_retained=True,
        revision_history_retained=True, events=[dict(event_id='settlement-1',settlement_ns=50,
        available_ns=51,rate='25.000000000000000000000000000001',rate_unit='bps')])
    def publish():
        unsigned = {k:v for k,v in manifest.items() if k != 'signature_b64'}
        (root/'message').write_bytes(FUNDING_DOMAIN + canonical_bytes(unsigned))
        (root/'public-test-seed.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+keys['SEED'])
        subprocess.run([str(exe),'pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(root/'public-test-seed.der'),
            '-in',str(root/'message'),'-out',str(root/'signature')],check=True,capture_output=True)
        data=canonical_bytes({**unsigned,'signature_b64':base64.b64encode((root/'signature').read_bytes()).decode()})
        (root/'funding.json').write_bytes(data)
        return sha256(data).hexdigest()
    return dict(manifest=manifest, policy=policy, verifier=verifier, root=root,
        trust_sha=sha256(canonical_bytes(trust)).hexdigest(), publish=publish, sha=publish())


def load(b, **kwargs):
    from strattester.research.financial_authenticated_funding import load_authenticated_funding
    args=dict(path=b['root']/'funding.json', expected_sha256=b['sha'],
        trust_store_path=b['root']/'trust.json', trust_store_sha256=b['trust_sha'],
        policy=b['policy'], verifier=b['verifier'])
    return load_authenticated_funding(**{**args,**kwargs})


def test_genuine_signature_preserves_decimal_and_cashflow_without_qualifying_history(tmp_path):
    from strattester.research.financial_evaluation import Trade, evaluate_ledger
    b=bundle(tmp_path); result=load(b)
    assert result.window.events[0].rate == b['manifest']['events'][0]['rate']
    report=evaluate_ledger([Trade('venue/perpetual/SOL',0,100,0.,1)],funding_windows=(result.window,))
    assert report['returns'] == [-.0025]
    assert report['funding_status']=='RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED'
    assert result.provenance['historical_truth']=='NOT_ESTABLISHED_BY_SIGNATURE'
    assert result.provenance['physical_g1']=='NOT_AUTHORIZED'
    from dataclasses import asdict
    from strattester.research.financial_authenticated_funding import FUNDING_SCHEMA_SHA256
    from strattester.research.financial_snapshot import canonical_bytes
    assert result.provenance['key_id']=='rfc-key'
    assert result.provenance['schema_sha256']==FUNDING_SCHEMA_SHA256
    assert result.provenance['signature_verifier_sha256']==b['verifier'].executable_sha256
    assert result.provenance['policy_canonical_sha256']==sha256(canonical_bytes({'version':1,**asdict(b['policy'])})).hexdigest()


@pytest.mark.parametrize('field,value', [('coherence_epoch_id','replayed'),('snapshot_id','other'),
    ('producer_build_sha','c'*40),('source_schema_sha256','c'*64),('knowledge_cutoff_ns',100.0),
    ('complete',1),('first_availability_retained',False),('revision_history_retained',False),
    ('version',True),('schema_sha256','0'*64),('end_ns',99)])
def test_signed_policy_or_history_mismatch_rejected(tmp_path, field, value):
    b=bundle(tmp_path);b['manifest'][field]=value;b['sha']=b['publish']()
    with pytest.raises(ValueError):load(b)


@pytest.mark.parametrize('change',[dict(rate=0.25),dict(rate='NaN'),dict(rate='1e-65'),
    dict(rate_unit='fraction'),dict(settlement_ns=101),dict(available_ns=101),dict(available_ns=49)])
def test_signed_malformed_or_future_event_rejected(tmp_path,change):
    b=bundle(tmp_path);b['manifest']['events'][0].update(change);b['sha']=b['publish']()
    with pytest.raises(ValueError):load(b)


@pytest.mark.parametrize('field,value',[('market_type','spot'),('symbol','OTHER'),('timeframe_ns',10.0)])
def test_partition_identity_never_aliased(tmp_path,field,value):
    b=bundle(tmp_path);b['manifest']['partition'][field]=value;b['sha']=b['publish']()
    with pytest.raises(ValueError):load(b)


def test_tampered_signature_trust_and_fixture_relabel_rejected(tmp_path):
    from strattester.research.financial_snapshot import canonical_bytes
    b=bundle(tmp_path);b['manifest']['signature_b64']=base64.b64encode(b'\x00'*64).decode()
    data=canonical_bytes(b['manifest']);(tmp_path/'funding.json').write_bytes(data)
    with pytest.raises(ValueError):load(b,expected_sha256=sha256(data).hexdigest())
    b['manifest']['scope']='PRODUCER_ATTESTED_RESEARCH';b['sha']=b['publish']()
    with pytest.raises(ValueError,match='fixture'):load(b,policy=replace(b['policy'],scope='PRODUCER_ATTESTED_RESEARCH'))
    (tmp_path/'trust.json').write_bytes(b'{}')
    with pytest.raises(ValueError):load(b)


def test_cancel_and_budget_refuse_before_signature_work(tmp_path,monkeypatch):
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_training import TrainingCancelled
    b=bundle(tmp_path)
    monkeypatch.setattr(OpenSSLVerifier,'verify',lambda *args:pytest.fail('verification must not run'))
    with pytest.raises(TrainingCancelled):load(b,cancel=lambda:True)
    b['manifest']['events']*=10001;b['sha']=b['publish']()
    with pytest.raises(ValueError,match='budget'):load(b)


def test_event_duplicates_and_exact_source_pin(tmp_path):
    b=bundle(tmp_path);b['manifest']['events']*=2;b['sha']=b['publish']()
    with pytest.raises(ValueError):load(b)
    with pytest.raises(ValueError):load(b,expected_sha256='0'*64)


def test_cli_pinned_policy_is_reachable_and_does_not_admit_research(tmp_path,capsys):
    from dataclasses import asdict
    import json
    from strattester.research.financial_snapshot import canonical_bytes
    from strattester.research_cli import main
    b=bundle(tmp_path)
    policy=canonical_bytes({'version':1,**asdict(b['policy'])})
    (tmp_path/'policy.json').write_bytes(policy)
    args=['verify-funding','--funding',str(tmp_path/'funding.json'),'--funding-sha256',b['sha'],
        '--policy',str(tmp_path/'policy.json'),'--policy-sha256',sha256(policy).hexdigest(),
        '--trust-store',str(tmp_path/'trust.json'),'--trust-store-sha256',b['trust_sha'],
        '--openssl-exe',str(b['verifier'].executable),'--openssl-sha256',b['verifier'].executable_sha256,
        '--scratch-root',str(tmp_path)]
    assert main(args)==0
    report=json.loads(capsys.readouterr().out)
    assert report['status']=='SIGNATURE_VERIFIED_ONLY'
    assert report['provenance']['historical_truth']=='NOT_ESTABLISHED_BY_SIGNATURE'
    assert report['provenance']['runtime_funding_admission']=='NOT_ENABLED'
    assert report['provenance']['policy_bytes_sha256']==sha256(policy).hexdigest()
    (tmp_path/'policy.json').write_bytes(b'{}')
    assert main(args)==2


@pytest.mark.parametrize('change',[dict(version=True),dict(extra='unknown'),dict(timeframe_ns=10.0)])
def test_policy_schema_is_exact_and_typed(tmp_path,change):
    from dataclasses import asdict
    from strattester.research.financial_snapshot import canonical_bytes
    from strattester.research.financial_authenticated_funding import load_funding_policy
    b=bundle(tmp_path);data=canonical_bytes({**{'version':1,**asdict(b['policy'])},**change})
    (tmp_path/'policy.json').write_bytes(data)
    with pytest.raises(ValueError):load_funding_policy(tmp_path/'policy.json',sha256(data).hexdigest())


def test_domain_replay_and_expired_key_rejected(tmp_path):
    import json
    from strattester.research.financial_snapshot import canonical_bytes
    b=bundle(tmp_path)
    # Reuse a genuine signature over a different domain, with the exact expected artifact hash.
    (tmp_path/'message').write_bytes(b'OTHER_PROTOCOL\x00'+canonical_bytes(b['manifest']))
    subprocess.run([str(b['verifier'].executable),'pkeyutl','-sign','-rawin','-keyform','DER',
        '-inkey',str(tmp_path/'public-test-seed.der'),'-in',str(tmp_path/'message'),'-out',str(tmp_path/'signature')],
        check=True,capture_output=True)
    bad={**b['manifest'],'signature_b64':base64.b64encode((tmp_path/'signature').read_bytes()).decode()}
    data=canonical_bytes(bad);(tmp_path/'funding.json').write_bytes(data)
    with pytest.raises(ValueError,match='signature'):load(b,expected_sha256=sha256(data).hexdigest())
    b['sha']=b['publish']()
    trust=json.loads((tmp_path/'trust.json').read_bytes());trust['keys'][0]['valid_until_ns']=105
    data=canonical_bytes(trust);(tmp_path/'trust.json').write_bytes(data)
    with pytest.raises(ValueError,match='expired'):load(b,trust_store_sha256=sha256(data).hexdigest())


def test_duplicate_json_keys_rejected_before_verifier(tmp_path,monkeypatch):
    from strattester.research.financial_signatures import OpenSSLVerifier
    b=bundle(tmp_path)
    data=(tmp_path/'funding.json').read_bytes().replace(b'"version":1',b'"version":1,"version":1')
    (tmp_path/'funding.json').write_bytes(data)
    monkeypatch.setattr(OpenSSLVerifier,'verify',lambda *a:pytest.fail('must not verify malformed JSON'))
    with pytest.raises(ValueError,match='duplicate'):load(b,expected_sha256=sha256(data).hexdigest())


def test_cancellation_after_signature_does_not_return_window(tmp_path,monkeypatch):
    from strattester.research.financial_signatures import OpenSSLVerifier
    from strattester.research.financial_training import TrainingCancelled
    b=bundle(tmp_path);cancelled=False;verify=OpenSSLVerifier.verify
    def wrapped(*args):
        nonlocal cancelled
        result=verify(*args);cancelled=True;return result
    monkeypatch.setattr(OpenSSLVerifier,'verify',wrapped)
    with pytest.raises(TrainingCancelled):load(b,cancel=lambda:cancelled)


def test_signed_cancelling_settlements_preserve_decimal_residual_under_small_context(tmp_path):
    from decimal import Decimal, localcontext, Context
    from strattester.research.financial_evaluation import Trade,evaluate_ledger
    b=bundle(tmp_path)
    rates=('10000','0.000000000000000000000000000001','-10000')
    b['manifest']['events']=[dict(event_id=str(i),settlement_ns=i*20,available_ns=i*20,
        rate=rate,rate_unit='bps') for i,rate in enumerate(rates,1)]
    b['sha']=b['publish']()
    with localcontext(Context(prec=100)):
        # Independent Decimal cashflow oracle from explicit signed fixture rates.
        expected=-sum((Decimal(rate) for rate in rates),Decimal(0))/Decimal(10000)
    with localcontext() as context:
        context.prec=6;context.Emax=2;context.Emin=-2
        funding=load(b)
        result=evaluate_ledger([Trade('venue/perpetual/SOL',0,100,0.,1)],funding_windows=(funding.window,))
    assert result['returns']==[float(expected)]==[-1e-34]
    # The exact same settled event bytes never depend on the decision timeframe.
    with pytest.raises(ValueError):load(b,policy=replace(b['policy'],timeframe_ns=20))
