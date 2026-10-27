"""CPU-only engineering evidence. PUBLIC keys/data; never real OOS performance.

Run from a clean exact-HEAD checkout with dev + CPU research dependencies.
The fixture implementation lives with tests intentionally: this command is a
software test harness, not an alternative market-data/production entrypoint.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import runpy
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise ValueError('clean exact-HEAD checkout required')
    target=args.output.resolve()
    from strattester.research.financial_snapshot import reject_linked_path,canonical_bytes
    reject_linked_path(target.parent)
    target.mkdir()  # exclusive: retain all prior evidence
    def deny(*a,**k):raise AssertionError('synthetic E2E attempted Python socket networking')
    socket.socket.connect=deny;socket.create_connection=deny
    import torch
    if torch.cuda.is_available():raise ValueError('CPU evidence cannot substitute for GPU qualification')
    fixture=runpy.run_path(str(ROOT/'tests/research/test_ml_oos_funding_session.py'))
    inputs_dir=target/'inputs';inputs_dir.mkdir()
    driver,data,funding_path,funding_pin=fixture['inputs'](inputs_dir)
    summary=driver['run'](data,target/'run',funding_bundle_path=funding_path,funding_bundle_sha256=funding_pin)
    report=json.loads((target/'run/report.json').read_bytes())
    assert report['real_oos']=='BLOCKED' and report['physical_g1']=='NOT_AUTHORIZED'
    assert summary['funding']=='SIGNED_SYNTHETIC_ONLY' and len(report['folds'])==2
    # Independent literal cashflow equation, with unit entry notional.
    for i,fold in enumerate(report['folds']):
        assert fold['checkpoint_reloaded'] and fold['calibration']['fit_partition']=='VALIDATION_ONLY'
        assert len(fold['control_scorecards'])==7 and fold['holdout_count']==6
        assert fold['test_count']==18 and len(fold['funding_adjusted_ledger']['rows'])==18
        for forecast,row in zip(fold['forecasts'],fold['funding_adjusted_ledger']['rows']):
            position=forecast['position']
            expected=position*math.expm1(forecast['forward_log_return'])-2*abs(position)*.0003-position*.002
            if not math.isclose(row['net_return'],expected,rel_tol=0.,abs_tol=1e-15):
                raise ValueError('independent synthetic ledger mismatch')
        for card in fold['control_scorecards'].values():
            for raw,row in zip(card['ledger']['rows'],card['funding_adjusted_ledger']['rows']):
                expected=raw['net_return']-raw['position']*.002
                if not math.isclose(row['net_return'],expected,rel_tol=0.,abs_tol=1e-15):
                    raise ValueError('independent synthetic baseline funding mismatch')
    # New interpreter re-verifies price signatures, loads checkpoints, predicts
    # ALL test rows and compares raw/calibrated metrics and exact forecasts.
    code="""import json,socket,sys
def deny(*a,**k):raise AssertionError('network attempted')
socket.socket.connect=deny;socket.create_connection=deny
from strattester.research.financial_checkpoint_replay import verify_walkforward_replay
from strattester.research.financial_signatures import OpenSSLVerifier
from pathlib import Path
v=OpenSSLVerifier(Path(sys.argv[7]),sys.argv[8],Path(sys.argv[9]))
print(json.dumps(verify_walkforward_replay(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],trust_store_path=sys.argv[5],trust_store_sha256=sys.argv[6],verifier=v)))
"""
    verifier=data[3]['verifier']
    result=subprocess.run([sys.executable,'-c',code,str(data[0]),data[1],str(target/'run/report.json'),
        summary['report_sha256'],str(inputs_dir/'trust.json'),data[3]['trust_sha'],
        str(verifier.executable),verifier.executable_sha256,str(inputs_dir)],
        cwd=ROOT,capture_output=True,text=True,timeout=120,check=True)
    replay=json.loads(result.stdout)
    if replay['forecasts_verified']!=36:raise ValueError('incomplete fresh-process replay')
    evidence={'version':1,'status':'SYNTHETIC_CPU_ENGINEERING_ONLY','head_sha':head,
        'tree_sha':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),
        'python':sys.version,'torch':torch.__version__,'platform':platform.platform(),
        'source_sha256':data[1],'funding_bundle_sha256':funding_pin,'summary':summary,
        'fold_counts':[{'train':f['train_count'],'validation':f['validation_count'],'test':f['test_count'],
                        'holdout':f['holdout_count']} for f in report['folds']],
        'fresh_process_replay':replay,'independent_ledger_oracle':'PASS_SYNTHETIC_ONLY',
        'network_guard':'PYTHON_SOCKETS_ONLY_NOT_OS_ISOLATION',
        'real_oos':'BLOCKED','funding_history':'BLOCKED','gpu':'BLOCKED_NOT_EXECUTED',
        'physical_g1':'NOT_AUTHORIZED','trading':'NO-GO','portfolio_performance_claim':'NONE'}
    files=[]
    for path in sorted(target.rglob('*')):
        if path.is_file():files.append({'path':path.relative_to(target).as_posix(),
            'bytes':path.stat().st_size,'sha256':sha256(path.read_bytes()).hexdigest()})
    evidence['files']=files
    raw=canonical_bytes(evidence);(target/'evidence.json').write_bytes(raw)
    (target/'SHA256SUMS').write_text(''.join(f"{f['sha256']}  {f['path']}\n" for f in files)
        +f"{sha256(raw).hexdigest()}  evidence.json\n",encoding='utf-8')
    print(json.dumps({'head_sha':head,'evidence_sha256':sha256(raw).hexdigest(),
        'status':evidence['status'],'real_oos':'BLOCKED','output':str(target)}))
    return 0


if __name__=='__main__':raise SystemExit(main())
