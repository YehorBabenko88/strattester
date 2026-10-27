"""Bounded, extraction-free CI artifact consistency; never execution authority."""
import io
from pathlib import PurePosixPath
import stat
import xml.etree.ElementTree as ET
import zipfile

from .financial_acceptance import execution_report, validate_execution
from .financial_contract import digest, integer
from .financial_executable_inventory import _local_path
from .financial_snapshot import bounded_json, verified_bytes


def audit_gate_archive(*, archive_path, metadata_path, metadata_sha256, expected_sha,
                      expected_run, expected_repository, gate, required_nodeids):
    digest(expected_sha,40); integer(expected_run,'run',1); integer(expected_repository,'repository',1)
    if gate not in ('core','data','math','cpu','training','security','integration'):
        raise ValueError('unknown artifact gate')
    if (type(required_nodeids) is not list or not required_nodeids
        or len(required_nodeids)>10000 or any(type(n) is not str or not 1<=len(n)<=2048 for n in required_nodeids)
        or len(set(required_nodeids))!=len(required_nodeids)):
        raise ValueError('invalid independent node manifest')
    meta=bounded_json(verified_bytes(_local_path(metadata_path),metadata_sha256,64*1024))
    if (type(meta.get('id')) is not int or meta['id']<1
        or meta.get('name')!='financial-'+gate+'-'+expected_sha or meta.get('expired') is not False
        or type(meta.get('digest')) is not str or not meta['digest'].startswith('sha256:')):
        raise ValueError('artifact metadata identity')
    run=meta.get('workflow_run')
    if (type(run) is not dict or type(run.get('id')) is not int or run['id']!=expected_run
        or type(run.get('repository_id')) is not int or run['repository_id']!=expected_repository
        or run.get('head_sha')!=expected_sha):
        raise ValueError('artifact workflow identity')
    size=integer(meta.get('size_in_bytes'),'archive bytes',1)
    if size>8*1024*1024:raise ValueError('archive size budget')
    archive=verified_bytes(_local_path(archive_path),meta['digest'][7:],8*1024*1024)
    if len(archive)!=size:raise ValueError('artifact size mismatch')
    names={gate+'.json',gate+'-pytest.json',gate+'.xml'}
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            infos=z.infolist()
            if len(infos)!=3 or {i.filename for i in infos}!=names:
                raise ValueError('artifact members differ from exact gate roster')
            if sum(i.file_size for i in infos)>16*1024*1024:
                raise ValueError('uncompressed artifact budget')
            bodies={}
            for info in infos:
                path=PurePosixPath(info.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename
                    or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1
                    or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                    or info.file_size>8*1024*1024):raise ValueError('artifact member type/budget')
                # Never use read() without a length: an attacker can understate
                # file_size while the compressed stream expands far beyond it.
                with z.open(info) as member:
                    body=member.read(info.file_size+1)
                if len(body)!=info.file_size:raise ValueError('artifact member length mismatch')
                bodies[info.filename]=body  # CRC checked, never extracted.
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError) as exc:
        raise ValueError('invalid artifact archive') from exc
    report=bounded_json(bodies[gate+'.json']);raw=bounded_json(bodies[gate+'-pytest.json'])
    expected=set(required_nodeids)
    validate_execution(report,expected_sha,gate,expected,len(expected))
    normalized=execution_report(raw,expected_sha,gate,raw.get('exitcode'))
    validate_execution(normalized,expected_sha,gate,expected,len(expected))
    collected=raw.get('summary',{}).get('collected')
    if type(collected) is not int or collected!=len(expected):
        raise ValueError('raw collected count differs from required roster')
    tests=raw.get('tests')
    if (type(tests) is not list or len(tests)!=len(expected)
        or set(normalized['nodeids'])!=expected or set(report['nodeids'])!=expected
        or normalized['passed']!=len(expected) or report['passed']!=len(expected)):
        raise ValueError('artifact raw/normalized node mismatch')
    # Explicitly reconcile summary categories; a forged normalized PASS cannot
    # suppress raw subtest parents, skips, deselection or counts.
    for field in ('passed','failed','errors','skipped','xfailed','xpassed','deselected','collected','exit_code'):
        if normalized[field]!=report[field]:raise ValueError('artifact accounting mismatch')
    xml=bodies[gate+'.xml']
    try:xml=xml.decode('utf-8')
    except UnicodeError as exc:raise ValueError('JUnit UTF-8 required') from exc
    if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('XML declaration/entity forbidden')
    try:cases=list(ET.fromstring(xml).iter('testcase'))
    except ET.ParseError as exc:raise ValueError('invalid JUnit') from exc
    if len(cases)!=len(expected):raise ValueError('JUnit case count')
    remaining=set(expected)
    for case in cases:
        if any(c.tag in ('error','failure','skipped') for c in case):raise ValueError('JUnit nonpassing case')
        suffix='::'+case.attrib.get('name','')
        matches=[n for n in remaining if n.endswith(suffix)
                 and n[:-len(suffix)].replace('.py','',1).replace('/','.').replace('::','.')==case.attrib.get('classname')]
        if len(matches)!=1:raise ValueError('JUnit node identity mismatch')
        remaining.remove(matches[0])
    if remaining:raise ValueError('JUnit missing node')
    return {'status':'BLOCKED','artifact_consistency':'VERIFIED_ONLY','sha':expected_sha,
        'run_id':expected_run,'gate':gate,'node_count':len(expected),'archive_sha256':meta['digest'][7:],
        'metadata_sha256':metadata_sha256,'evidence_authenticity':'UNVERIFIED_SELF_REPORT',
        'limitations':['NO_JOB_EXECUTION_ATTESTATION','NO_EXTERNAL_OR_PHYSICAL_AUTHORITY'],
        'physical_g1':'NOT_AUTHORIZED','deployment':'NO-GO','trading':'NO-GO'}
