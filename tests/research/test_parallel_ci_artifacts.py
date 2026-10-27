import hashlib
import io
import json
import zipfile

import pytest

from strattester.research.financial_acceptance import execution_report

HEAD='a'*40
NODE='tests/test_sample.py::Sample::test_one'


def fixture(root, mutation=None):
    raw=dict(exitcode=0,summary=dict(passed=1,total=1,collected=1),
             tests=[dict(nodeid=NODE,outcome='passed',call=dict(outcome='passed'))])
    normalized=execution_report(raw,HEAD,'security',0)
    xml=b'<testsuites><testsuite><testcase classname="tests.test_sample.Sample" name="test_one"/></testsuite></testsuites>'
    if mutation=='raw_skip': raw['tests'][0]['outcome']='skipped'
    if mutation=='summary_substitution':raw['summary']['passed']=0
    if mutation=='collected_substitution':raw['summary']['collected']=2
    if mutation=='junit_skip':xml=xml.replace(b'/>',b'><skipped/></testcase>',1)
    if mutation=='xml_entity':xml=b'<!DOCTYPE x [<!ENTITY a "secret">]>'+xml
    if mutation=='xml_entity_utf16':xml=('<!DOCTYPE x [<!ENTITY a "secret">]>'+xml.decode()).encode('utf-16')
    members={'security.json':json.dumps(normalized).encode(),'security-pytest.json':json.dumps(raw).encode(),'security.xml':xml}
    if mutation=='traversal':members['../escape']=b'x'
    if mutation=='duplicate':members['SECURITY.json']=members['security.json']
    if mutation=='large':members['security.xml']=b'x'*(8*1024*1024+1)
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        for name,body in members.items():z.writestr(name,body)
    artifact=root/'archive.zip';artifact.write_bytes(data.getvalue())
    meta=dict(id=1,name='financial-security-'+HEAD,size_in_bytes=len(data.getvalue()),
              digest='sha256:'+hashlib.sha256(data.getvalue()).hexdigest(),expired=False,
              workflow_run=dict(id=10,head_sha=HEAD,repository_id=20))
    if mutation=='run':meta['workflow_run']['id']=11
    if mutation=='hash':meta['digest']='sha256:'+'0'*64
    metadata=root/'metadata.json';metadata.write_text(json.dumps(meta))
    return dict(archive_path=str(artifact),metadata_path=str(metadata),
        metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),expected_sha=HEAD,
        expected_run=10,expected_repository=20,gate='security',required_nodeids=[NODE])


def test_artifact_consistency_is_never_execution_or_physical_authority(tmp_path):
    from strattester.research.financial_ci_artifacts import audit_gate_archive
    result=audit_gate_archive(**fixture(tmp_path))
    assert result['status']=='BLOCKED'
    assert result['artifact_consistency']=='VERIFIED_ONLY'
    assert result['node_count']==1 and result['physical_g1']=='NOT_AUTHORIZED'
    assert sorted(p.name for p in tmp_path.iterdir())==['archive.zip','metadata.json']


@pytest.mark.parametrize('mutation',['raw_skip','summary_substitution','junit_skip','xml_entity',
    'traversal','duplicate','large','run','hash','collected_substitution','xml_entity_utf16'])
def test_artifact_attacks_fail_closed(tmp_path,mutation):
    from strattester.research.financial_ci_artifacts import audit_gate_archive
    with pytest.raises(ValueError):audit_gate_archive(**fixture(tmp_path,mutation))


def test_pinned_cli_audit_is_read_only_and_blocked(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    args=fixture(tmp_path)
    manifest=tmp_path/'required.json';manifest.write_text(json.dumps({'security':{'nodeids':[NODE]}}))
    script=Path(__file__).resolve().parents[2]/'scripts/audit_qualification_artifact.py'
    command=[sys.executable,str(script),'--archive',args['archive_path'],'--metadata',args['metadata_path'],
        '--metadata-sha256',args['metadata_sha256'],'--required-manifest',str(manifest),
        '--required-manifest-sha256',hashlib.sha256(manifest.read_bytes()).hexdigest(),
        '--sha',HEAD,'--gate','security','--run','10','--repository','20']
    result=subprocess.run(command,capture_output=True,text=True,timeout=20)
    assert result.returncode==2 and not result.stderr
    output=json.loads(result.stdout)
    assert output['artifact_consistency']=='VERIFIED_ONLY' and output['status']=='BLOCKED'


def test_member_reads_are_bounded_even_if_zip_headers_lie(tmp_path,monkeypatch):
    from strattester.research.financial_ci_artifacts import audit_gate_archive
    args=fixture(tmp_path);original=zipfile.ZipExtFile.read;calls=[]
    def read(stream,n=-1):
        assert 0<=n<=8*1024*1024+1,'unbounded decompression read'
        calls.append(n)
        return original(stream,n)
    monkeypatch.setattr(zipfile.ZipExtFile,'read',read)
    assert audit_gate_archive(**args)['status']=='BLOCKED'
    assert len(calls)==3
