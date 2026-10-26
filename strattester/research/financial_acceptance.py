"""Fail-closed accounting. Workflow green is not system acceptance."""
from .financial_contract import digest


def execution_report(payload,sha,gate,exit_code):
    """Normalize pytest-json-report's parent-case outcomes without losing subtests.

    pytest 9 marks an all-successful unittest subTest parent as 'subtests
    passed', rather than 'passed'. Failed/skipped/xfail subtests do not qualify.
    Keep the original summary for independent inspection.
    """
    summary=payload.get('summary',{})
    names=('passed','subtests passed','failed','error','skipped','xfailed','xpassed','deselected','total')
    if any(type(summary.get(k,0)) is not int or summary.get(k,0)<0 for k in names):
        raise ValueError('invalid raw accounting')
    passed=summary.get('passed',0)+summary.get('subtests passed',0)
    nodes=[t['nodeid'] for t in payload.get('tests',[]) if t.get('outcome') in ('passed','subtests passed')
           and t.get('call',{}).get('outcome')=='passed']
    return {'schema':1,'sha':sha,'gate':gate,'status':'PASS','exit_code':exit_code,
            'passed':passed,'failed':summary.get('failed',0),'errors':summary.get('error',0),
            'skipped':summary.get('skipped',0),'xfailed':summary.get('xfailed',0),'xpassed':summary.get('xpassed',0),
            'deselected':summary.get('deselected',0),'collected':summary.get('total',0),
            'nodeids':nodes,'raw_summary':summary}


def validate_execution(report, sha, gate, required_nodeids, minimum):
    digest(sha,40)
    if (not isinstance(report,dict) or type(report.get('schema')) is not int or report.get('schema')!=1 or report.get('sha')!=sha
        or report.get('gate')!=gate or report.get('status')!='PASS'):
        raise ValueError('missing/stale/blocked gate identity')
    for key in ('passed','failed','errors','skipped','xfailed','xpassed','deselected','collected','exit_code'):
        if type(report.get(key)) is not int or report[key]<0:raise ValueError('invalid test accounting')
    if (any(report[k] for k in ('failed','errors','skipped','xfailed','xpassed','deselected','exit_code'))
        or report['passed']<minimum or report['collected']!=report['passed']):raise ValueError('incomplete execution')
    nodes=report.get('nodeids')
    if (type(nodes) is not list or len(nodes)!=len(set(nodes)) or len(nodes)!=report['passed']
        or not set(required_nodeids).issubset(nodes)):
        raise ValueError('missing required test execution')
    return True


# These facts have no implemented trusted verifier in this candidate. Caller
# supplied strings must never authorize a physical trial or promote readiness.
MANDATORY_EXTERNAL = frozenset(('grid_coherent_snapshot','real_oos','gpu','full_upstream_equivalence',
                               'windows_native_isolation','physical_g0','owner_g1_authorization'))


def aggregate(reports,sha,required_gates,*,external,job_result='success'):
    from pathlib import Path
    import json
    digest(sha,40)
    manifest=json.loads((Path(__file__).resolve().parents[2]/'scripts/financial-gate-manifest.json').read_text())
    failed=[]
    if job_result!='success':failed.append('workflow jobs did not complete successfully')
    if set(required_gates)!=set(manifest) or set(reports)!=set(manifest):failed.append('missing/extra gate')
    for gate,spec in manifest.items():
        try:
            validate_execution(reports[gate],sha,gate,spec['nodeids'],spec['minimum'])
            if set(reports[gate]['nodeids'])!=set(spec['nodeids']):raise ValueError('extra execution nodes')
        except (KeyError,ValueError,TypeError,AttributeError):failed.append(gate)
    if type(external) is not dict or any(v not in ('PASS','BLOCKED','FAIL') for v in external.values()):
        failed.append('invalid external state')
        external={}
    if any(v=='FAIL' for v in external.values()):failed.append('external failure')
    # Evidence authenticity is outside self-reported JSON. Until an independently
    # trusted producer/CI verifier exists, no input can clear these requirements.
    effective={name:('FAIL' if external.get(name)=='FAIL' else 'BLOCKED') for name in MANDATORY_EXTERNAL}
    return {'schema':1,'sha':sha,'status':'FAIL' if failed else 'BLOCKED',
            'trading':'NO-GO','physical_g1':'NOT_AUTHORIZED','failed':failed,
            'external':effective,'claimed_external':external,
            'evidence_authenticity':'UNVERIFIED_SELF_REPORT',
            'gates':{name:r.get('status','FAIL') for name,r in reports.items() if isinstance(r,dict)}}
