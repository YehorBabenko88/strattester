"""Bounded, extraction-free CI artifact consistency; never execution authority."""
import io
from pathlib import PurePosixPath
import stat
import struct
import re
import zlib
import xml.etree.ElementTree as ET
import zipfile

from .financial_acceptance import execution_report, validate_execution
from .financial_contract import digest, integer
from .financial_executable_inventory import _local_path
from .financial_snapshot import bounded_json, verified_bytes


def _member_bytes(archive,info,limit):
    """Decode bounded ZIP32 bytes independently of ZipExtFile's size clamp."""
    start=info.header_offset
    if start<0 or limit<0 or limit>len(archive) or start+30>limit:raise ValueError('ZIP local header bounds')
    h=struct.unpack_from('<4s5H3L2H',archive,start)
    if h[0]!=b'PK\x03\x04' or h[2]!=info.flag_bits or h[3]!=info.compress_type or info.extract_version>20:
        raise ValueError('ZIP local/central contract')
    offset=start+30+h[9]+h[10];end=offset+info.compress_size
    if offset>limit or end>limit or archive[start+30:start+30+h[9]]!=info.filename.encode('ascii'):
        raise ValueError('ZIP member extent/name')
    if h[2]&8:
        pos=end+4 if archive[end:end+4]==b'PK\x07\x08' else end
        if pos+12>limit or struct.unpack_from('<3L',archive,pos)!=(info.CRC,info.compress_size,info.file_size):
            raise ValueError('ZIP data descriptor mismatch')
    elif h[6:9]!=(info.CRC,info.compress_size,info.file_size):
        raise ValueError('ZIP local/central size/CRC mismatch')
    compressed=archive[offset:end]
    if info.compress_type==zipfile.ZIP_STORED:body=compressed
    else:
        decoder=zlib.decompressobj(-15)
        try:body=decoder.decompress(compressed,info.file_size+1)
        except zlib.error as exc:raise ValueError('ZIP invalid deflate stream') from exc
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('ZIP incomplete/extra deflate stream')
    if len(body)!=info.file_size or zlib.crc32(body)!=info.CRC:
        raise ValueError('ZIP expanded length/CRC mismatch')
    return body


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
            ordered=sorted(infos,key=lambda i:i.header_offset)
            for index,info in enumerate(ordered):
                path=PurePosixPath(info.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename or ':' in info.filename
                    or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1
                    or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                    or info.file_size>8*1024*1024):raise ValueError('artifact member type/budget')
                limit=ordered[index+1].header_offset if index+1<len(ordered) else z.start_dir
                bodies[info.filename]=_member_bytes(archive,info,limit)
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
    for test in tests:
        if any(type(test.get(phase)) is not dict or test[phase].get('outcome')!='passed'
               for phase in ('setup','call','teardown')):
            raise ValueError('raw pytest phase missing/nonpassing')
    # Explicitly reconcile summary categories; a forged normalized PASS cannot
    # suppress raw subtest parents, skips, deselection or counts.
    for field in ('passed','failed','errors','skipped','xfailed','xpassed','deselected','collected','exit_code'):
        if normalized[field]!=report[field]:raise ValueError('artifact accounting mismatch')
    xml=bodies[gate+'.xml']
    try:xml=xml.decode('utf-8')
    except UnicodeError as exc:raise ValueError('JUnit UTF-8 required') from exc
    if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('XML declaration/entity forbidden')
    try:root=ET.fromstring(xml);cases=list(root.iter('testcase'))
    except ET.ParseError as exc:raise ValueError('invalid JUnit') from exc
    if len(cases)!=len(expected):raise ValueError('JUnit case count')
    remaining=set(expected);case_nodes={}
    for case in cases:
        if any(c.tag in ('error','failure','skipped') for c in case):raise ValueError('JUnit nonpassing case')
        suffix='::'+case.attrib.get('name','')
        matches=[n for n in remaining if n.endswith(suffix)
                 and n[:-len(suffix)].replace('.py','',1).replace('/','.').replace('::','.')==case.attrib.get('classname')]
        if len(matches)!=1:raise ValueError('JUnit node identity mismatch')
        remaining.remove(matches[0])
        case_nodes[id(case)]=matches[0]
    if remaining:raise ValueError('JUnit missing node')
    subtests={t['nodeid'] for t in tests if t['outcome']=='subtests passed'}
    counter_notes=[]
    for suite in root.iter():
        if suite.tag not in ('testsuite','testsuites'):continue
        for name in ('failures','errors','skipped','disabled','tests'):
            value=suite.get(name)
            if value is None:continue
            if not re.fullmatch('[0-9]{1,9}',value):raise ValueError('JUnit counter type/budget')
            number=int(value)
            if name!='tests' and number:raise ValueError('JUnit nonpassing suite counter')
            if name=='tests':
                nodes={case_nodes[id(c)] for c in suite.iter('testcase')}
                # pytest counts successful subtest assertions in tests= while
                # emitting one testcase per parent. Preserve, never sum as nodes.
                if number<len(nodes) or (number>len(nodes) and not nodes.intersection(subtests)):
                    raise ValueError('JUnit tests counter mismatch')
                counter_notes.append({'declared_tests':number,'parent_nodes':len(nodes),
                                      'subtest_assertion_surplus':number-len(nodes)})
    return {'status':'BLOCKED','artifact_consistency':'VERIFIED_ONLY','sha':expected_sha,
        'run_id':expected_run,'gate':gate,'node_count':len(expected),'archive_sha256':meta['digest'][7:],
        'metadata_sha256':metadata_sha256,'junit_counter_notes':counter_notes,
        'evidence_authenticity':'UNVERIFIED_SELF_REPORT',
        'limitations':['NO_JOB_EXECUTION_ATTESTATION','NO_EXTERNAL_OR_PHYSICAL_AUTHORITY'],
        'physical_g1':'NOT_AUTHORIZED','deployment':'NO-GO','trading':'NO-GO'}
