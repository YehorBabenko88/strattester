"""Run one pinned test manifest and publish fail-closed same-HEAD evidence."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from strattester.research.financial_acceptance import validate_execution, aggregate, execution_report
from strattester.research.financial_contract import digest


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--gate',required=True)
    parser.add_argument('--sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    digest(args.sha,40)
    os.chdir(ROOT)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if actual!=args.sha:raise ValueError('stale checkout SHA')
    dirty=subprocess.check_output(['git','status','--porcelain'],text=True).strip()
    if dirty:raise ValueError('uncommitted tracked changes cannot certify a HEAD')
    specs=json.loads((ROOT/'scripts/financial-gate-manifest.json').read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    if args.gate=='aggregate':
        reports={}
        for gate in specs:
            p=args.output/f'{gate}.json'
            if p.is_file():
                reports[gate]=json.loads(p.read_text())
                try:validate_execution(reports[gate],args.sha,gate,set(specs[gate]['nodeids']),specs[gate]['minimum'])
                except ValueError:reports[gate]['status']='FAIL'
        result=aggregate(reports,args.sha,set(specs),external={
            'grid_coherent_snapshot':'BLOCKED','real_oos':'BLOCKED','gpu':'BLOCKED','full_upstream_equivalence':'BLOCKED'},
            job_result='success' if os.environ.get('ENGINEERING_RESULT')=='success' and os.environ.get('NATIVE_RESULT')=='success' else 'incomplete')
        (args.output/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 0 if result['status']=='PASS' else 2
    if args.gate not in specs:raise ValueError('unknown gate')
    import torch  # All hosted gates explicitly install the CPU dependency.
    if torch.cuda.is_available():raise ValueError('CPU gate cannot substitute for GPU evidence')
    spec=specs[args.gate]
    # Select exact nodes: no -k deselection can hide a critical test.
    # GPU nodes and Linux-inapplicable Windows lifecycle are explicitly absent
    # from this CPU manifest and stay tracked by separate BLOCKED requirements.
    with tempfile.TemporaryDirectory(prefix='financial-gate-') as scratch:
        raw=Path(scratch)/'pytest.json'
        nodefile=Path(scratch)/'nodes.txt'
        nodefile.write_text('\n'.join(spec['nodeids'])+'\n')
        command=[sys.executable,'-m','pytest','-q','-o','addopts=--import-mode=importlib',
                 '--strict-markers','--json-report',f'--json-report-file={raw}',
                 f'--junitxml={args.output.resolve()/ (args.gate+".xml")}',
                 f'--basetemp={Path(scratch)/"cases"}',f'@{nodefile}']
        completed=subprocess.run(command,check=False,timeout=900)
        payload=json.loads(raw.read_text()) if raw.is_file() else {}
    (args.output/f'{args.gate}-pytest.json').write_text(json.dumps(payload,indent=2)+'\n')
    report=execution_report(payload,actual,args.gate,completed.returncode)
    report.update(python=sys.version,torch=torch.__version__,platform=sys.platform)
    try:validate_execution(report,actual,args.gate,set(spec['nodeids']),spec['minimum'])
    except ValueError as exc:report['status']='FAIL';report['reason']=str(exc)
    (args.output/f'{args.gate}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"{args.gate}: {report['status']}; {report['passed']} passed; {report['skipped']} skipped; SHA {actual}")
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
