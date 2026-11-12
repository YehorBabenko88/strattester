"""Single bounded offline invocation; writes only a new owned result directory."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import time
from .adapter import load_snapshot, write_snapshot
from .synthetic import generate
from .features import build_examples
from .evaluation import run_evaluation, digest


def _write(path,value):
    with path.open('w',encoding='utf8') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)


def source_hashes():
    root=Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root/'mwi_offline').glob('*.py'))}


def run_research(output,source_head,n=6000,snapshot=None,pin=None):
    if type(n) is not int or not 60<=n<=10000:raise ValueError('BAR_RESOURCE_CAP')
    start=time.perf_counter();cpu=time.process_time();output=Path(output)
    output.mkdir() # exclusive new directory: preserve prior evidence
    checkpoint={'stage':'INPUT_VALIDATION','status':'IN_PROGRESS','export_authorized':False,'database_access':False}
    _write(output/'checkpoint.json',checkpoint)
    try:
        if snapshot is None:
            bars=generate(n=n)
            pin=write_snapshot(output/'dataset',bars,source_head)
            dataset=load_snapshot(output/'dataset',pin,source_head,allow_synthetic=True)
        else:
            if pin is None:raise ValueError('EXTERNAL_MANIFEST_PIN_REQUIRED')
            dataset=load_snapshot(snapshot,pin,source_head,allow_synthetic=True)
            bars=dataset['bars']
        checkpoint.update(stage='INPUT_VERIFIED',manifest_sha256=pin)
        _write(output/'checkpoint.json',checkpoint)
        built=build_examples(bars)
        if len(built['examples'])>256:raise ValueError('EXAMPLE_RESOURCE_CAP')
        checkpoint.update(stage='EXAMPLES_FROZEN',examples_sha256=digest(built))
        _write(output/'checkpoint.json',checkpoint)
        result=run_evaluation(built['examples'],embargo=12*60000,evaluation_as_of=max(b['available_ms'] for b in bars))
        if time.perf_counter()-start>60:raise ValueError('WALL_BUDGET_EXCEEDED')
        final=result['final']['metrics']
        missing_classes=[c for c,nc in final['baseline']['class_counts'].items() if nc==0]
        status='MWI_OFFLINE_RESEARCH_READY' if not missing_classes else 'OFFLINE_PROTOCOL_TESTED_CLASS_SUPPORT_BLOCKED'
        report={'schema':'mwi.offline.research.result.v1','status':status,
                'scope':'SYNTHETIC_ONLY_NO_MARKET_EDGE_OR_RUNTIME_ADMISSION',
                'source_head_context':source_head,'source_head_role':'caller_supplied_source_context_not_authentication',
                'source_file_sha256':source_hashes(),'python':platform.python_version(),
                'dataset':{'manifest_sha256':pin,'content_dataset_id':dataset['manifest']['dataset_id'],
                           'rows':len(bars),'evidence_class':dataset['manifest']['evidence_class']},
                'features':built['feature_names'],'cohort_counts':built['counts'],
                'examples_sha256':digest(built),'evaluation':result,
                'missing_final_classes':missing_classes,
                'snapshot_integration':{'normalized_synthetic_read':'TESTED','historical_native_admission':'BLOCKED_EXTERNAL_PROVENANCE_AND_OWNER_ADAPTER',
                                        'production_postgres':'NEVER_CONNECTED','export':'NOT_AUTHORIZED_NOT_RUN'},
                'real_trading':False,'root_runtime_changed':False}
        report['reproducible_sha256']=digest(report)
        _write(output/'results.json',report)
        _write(output/'resources.json',{'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
                                      'gpu':0,'processes':1,'max_input_bars':10000,'max_examples':256,
                                      'wall_postcondition_seconds':60,'physical_hard_quota':'NOT_CLAIMED'})
        checkpoint.update(stage='COMPLETE',status=status,result_sha256=hashlib.sha256((output/'results.json').read_bytes()).hexdigest(),
                          reproducible_sha256=report['reproducible_sha256'])
        _write(output/'checkpoint.json',checkpoint)
        return report
    except Exception as exc:
        checkpoint.update(status='FAILED',error_type=type(exc).__name__,error_code=str(exc))
        _write(output/'checkpoint.json',checkpoint)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--source-head',required=True)
    p.add_argument('--bars',type=int,default=6000);p.add_argument('--snapshot');p.add_argument('--manifest-sha256')
    a=p.parse_args()
    r=run_research(a.output,a.source_head,n=a.bars,snapshot=a.snapshot,pin=a.manifest_sha256)
    print(json.dumps({'status':r['status'],'reproducible_sha256':r['reproducible_sha256'],
                      'final':r['evaluation']['final']['metrics']},indent=2))
