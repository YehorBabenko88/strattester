"""Signed synthetic funding joined to exact forecast markets/timeframes."""
from dataclasses import asdict
from hashlib import sha256
import base64
import json
from pathlib import Path
import runpy
import subprocess

import pytest
from strattester.research.financial_snapshot import canonical_bytes


def inputs(root):
    fixture=runpy.run_path(str(Path(__file__).with_name('test_financial_walkforward_session.py')))
    data=list(fixture['source'](root))
    path,pin,payload,keys,bootstrap=data
    from strattester.research.financial_authenticated_funding import FUNDING_SCHEMA_SHA256, FUNDING_DOMAIN, FundingPolicy
    from strattester.research.financial_contract import Instrument
    key_fixture=runpy.run_path(str(Path(__file__).with_name('signed_export_fixture.py')))
    trust={'version':1,'keys':[dict(producer_id='fixture-funding',key_id='public',
        public_key_b64=base64.b64encode(key_fixture['PUBLIC']).decode(),valid_from_ns=0,valid_until_ns=10000,revoked=False)]}
    (root/'funding-trust.json').write_bytes(canonical_bytes(trust))
    entries=[]
    for symbol in ('BTCUSDT','ETHUSDT','SOLUSDT'):
        for tf in (60,120):
            policy=FundingPolicy('fixture-funding','a'*40,'synthetic','b'*64,'funding-cut',
                'epoch-fixture',Instrument('bybit','linear',symbol),tf,0,4800,4800,4810)
            manifest=dict(version=1,schema_sha256=FUNDING_SCHEMA_SHA256,
                **{k:v for k,v in asdict(policy).items() if k not in ('instrument','timeframe_ns','verification_ns')},
                key_id='public',issued_at_ns=4801,partition={**asdict(policy.instrument),'timeframe_ns':tf},
                complete=True,first_availability_retained=True,revision_history_retained=True,
                events=[dict(event_id=f'event-{t}',settlement_ns=t,available_ns=t,rate='20',rate_unit='bps')
                        for t in (2640,3000,3360,3720,4080,4440)])
            (root/'message').write_bytes(FUNDING_DOMAIN+canonical_bytes(manifest))
            (root/'key.der').write_bytes(bytes.fromhex('302e020100300506032b657004220420')+key_fixture['SEED'])
            subprocess.run([str(keys['verifier'].executable),'pkeyutl','-sign','-rawin','-keyform','DER',
                '-inkey',str(root/'key.der'),'-in',str(root/'message'),'-out',str(root/'signature')],check=True,capture_output=True)
            manifest['signature_b64']=base64.b64encode((root/'signature').read_bytes()).decode()
            name=f'funding-{symbol}-{tf}.json';raw=canonical_bytes(manifest);(root/name).write_bytes(raw)
            policy_name=f'policy-{symbol}-{tf}.json';praw=canonical_bytes({'version':1,**asdict(policy)});(root/policy_name).write_bytes(praw)
            entries.append(dict(path=name,sha256=sha256(raw).hexdigest(),policy_path=policy_name,
                policy_sha256=sha256(praw).hexdigest(),trust_store_path='funding-trust.json',
                trust_store_sha256=sha256(canonical_bytes(trust)).hexdigest()))
    bundle={'version':1,'scope':'SYNTHETIC_ENGINEERING_ONLY','entries':entries}
    raw=canonical_bytes(bundle);(root/'funding-bundle.json').write_bytes(raw)
    return fixture,data,root/'funding-bundle.json',sha256(raw).hexdigest()


def test_signed_synthetic_funding_reconciles_every_test_cashflow(tmp_path):
    fixture,data,path,pin=inputs(tmp_path)
    result=fixture['run'](data,tmp_path/'out',funding_bundle_path=path,funding_bundle_sha256=pin)
    report=json.loads((tmp_path/'out'/'report.json').read_bytes())
    assert result['funding']=='SIGNED_SYNTHETIC_ONLY'
    assert report['real_oos']=='BLOCKED' and report['trading']=='NO-GO'
    assert report['funding']['historical_truth']=='NOT_ESTABLISHED_BY_SIGNATURE'
    for fold in report['folds']:
        ledger=fold['funding_adjusted_ledger']
        assert len(ledger['rows'])==18
        for raw,adjusted in zip(fold['ledger']['rows'],ledger['rows']):
            assert adjusted['funding_cashflow']==pytest.approx(-raw['position']*.002)
            assert adjusted['net_return']==pytest.approx(raw['net_return']-raw['position']*.002)
        for card in fold['control_scorecards'].values():
            for raw,adjusted in zip(card['ledger']['rows'],card['funding_adjusted_ledger']['rows']):
                assert adjusted['net_return']==pytest.approx(raw['net_return']-raw['position']*.002)


def test_fresh_process_replays_all_predictions_and_rejects_changed_checkpoint(tmp_path):
    import sys
    fixture,data,path,pin=inputs(tmp_path)
    summary=fixture['run'](data,tmp_path/'out',funding_bundle_path=path,funding_bundle_sha256=pin)
    v=data[3]['verifier']
    code="""import json,sys
from strattester.research.financial_checkpoint_replay import verify_walkforward_replay
from strattester.research.financial_signatures import OpenSSLVerifier
from pathlib import Path
r=verify_walkforward_replay(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],trust_store_path=sys.argv[5],trust_store_sha256=sys.argv[6],verifier=OpenSSLVerifier(Path(sys.argv[7]),sys.argv[8],Path(sys.argv[9])))
print(json.dumps(r))
"""
    command=[sys.executable,'-c',code,str(data[0]),data[1],str(tmp_path/'out/report.json'),summary['report_sha256'],
        str(tmp_path/'trust.json'),data[3]['trust_sha'],str(v.executable),v.executable_sha256,str(tmp_path)]
    completed=subprocess.run(command,capture_output=True,text=True,timeout=120)
    assert completed.returncode==0,completed.stderr
    assert json.loads(completed.stdout)['forecasts_verified']==36
    (tmp_path/'out/fold-000.json').write_bytes(b'{}')
    completed=subprocess.run(command,capture_output=True,text=True,timeout=120)
    assert completed.returncode!=0


@pytest.mark.parametrize('mutation',['missing','pin','duplicate','scope','timeframe'])
def test_funding_bundle_failures_never_publish(tmp_path,mutation):
    fixture,data,path,pin=inputs(tmp_path)
    bundle=json.loads(path.read_bytes())
    if mutation=='missing':bundle['entries'].pop()
    if mutation=='pin':bundle['entries'][0]['sha256']='0'*64
    if mutation=='duplicate':bundle['entries'].append(bundle['entries'][0])
    if mutation=='scope':bundle['scope']='PRODUCER_ATTESTED_RESEARCH'
    if mutation=='timeframe':
        policy=tmp_path/bundle['entries'][0]['policy_path']
        value=json.loads(policy.read_bytes());value['timeframe_ns']=999
        raw=canonical_bytes(value);policy.write_bytes(raw);bundle['entries'][0]['policy_sha256']=sha256(raw).hexdigest()
    raw=canonical_bytes(bundle);path.write_bytes(raw);pin=sha256(raw).hexdigest()
    with pytest.raises(ValueError):fixture['run'](data,tmp_path/'out',funding_bundle_path=path,funding_bundle_sha256=pin)
    assert not (tmp_path/'out').exists()
    assert not list(tmp_path.glob('.walkforward-*'))
