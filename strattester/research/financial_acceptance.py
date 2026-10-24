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
    if (not isinstance(report,dict) or report.get('schema')!=1 or report.get('sha')!=sha
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


def aggregate(reports,sha,required_gates,*,external,job_result='success'):
    digest(sha,40)
    failed=[]
    if job_result!='success':failed.append('workflow jobs did not complete successfully')
    if set(reports)!=set(required_gates):failed.append('missing/extra gate')
    for gate in required_gates:
        try:
            r=reports[gate]
            # Required node manifests are enforced by the producer gate script.
            # Aggregator enforces SHA/identity/counts again, never trusts status alone.
            validate_execution(r,sha,gate,r.get('nodeids',()),1)
        except (KeyError,ValueError,TypeError,AttributeError):failed.append(gate)
    if any(v not in ('PASS','BLOCKED','FAIL') for v in external.values()):failed.append('invalid external state')
    if any(v=='FAIL' for v in external.values()):failed.append('external failure')
    status='FAIL' if failed else ('BLOCKED' if any(v!='PASS' for v in external.values()) else 'PASS')
    return {'schema':1,'sha':sha,'status':status,'trading':'NO-GO','failed':failed,'external':external,
            'gates':{name:r.get('status','FAIL') for name,r in reports.items()}}
