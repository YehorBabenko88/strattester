from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch
import pytest


def setup(tmp_path):return runpy.run_path(str(Path(__file__).with_name('test_financial_attested_inference.py')))['setup'](tmp_path)


def test_stream_is_lazy_bounded_and_does_not_materialize_requests(tmp_path,monkeypatch):
    from strattester.research.financial_offline_jobs import OfflineJob,stream_offline_jobs
    b,r=setup(tmp_path);consumed=[]
    def source():
        for i in range(10000):consumed.append(i);yield OfflineJob(r,b['policy'])
    stream=stream_offline_jobs(source(),verifier=b['verifier'],max_requests=1)
    assert consumed==[]
    assert next(stream).prediction.instrument==r.instrument and consumed==[0]
    with pytest.raises(ValueError,match='request budget'):next(stream)
    assert consumed==[0,1]


def test_cancellation_between_requests_precedes_next_input(tmp_path):
    from strattester.research.financial_offline_jobs import OfflineJob,stream_offline_jobs
    from strattester.research.financial_training import TrainingCancelled
    b,r=setup(tmp_path);state={'cancel':False};consumed=[]
    def source():
        for i in range(3):consumed.append(i);yield OfflineJob(r,b['policy'])
    stream=stream_offline_jobs(source(),verifier=b['verifier'],cancel=lambda:state['cancel'])
    next(stream);state['cancel']=True
    with pytest.raises(TrainingCancelled):next(stream)
    assert consumed==[0]


def test_stream_cumulative_budget_is_charged_before_more_inference(tmp_path):
    from strattester.research.financial_offline_jobs import OfflineJob,stream_offline_jobs,MAX_REQUEST_BYTES
    b,r=setup(tmp_path)
    stream=stream_offline_jobs([OfflineJob(r,b['policy'])]*2,verifier=b['verifier'],max_input_bytes=MAX_REQUEST_BYTES)
    next(stream)
    with pytest.raises(ValueError,match='input budget'):next(stream)


def test_atomic_result_replay_recomputes_expected_bytes_and_rejects_tamper(tmp_path):
    from strattester.research.financial_offline_jobs import publish_result
    job=sha256(b'job').hexdigest();payload={'prediction':.1,'physical_g1':'NOT_AUTHORIZED'}
    first=publish_result(tmp_path,job,payload)
    assert publish_result(tmp_path,job,payload)['status']=='REPLAY_VERIFIED'
    Path(first['path']).write_bytes(b'{"forged":true}')
    with pytest.raises(ValueError):publish_result(tmp_path,job,payload)
    assert Path(first['path']).read_bytes()==b'{"forged":true}'


def test_interrupted_complete_stage_is_recovered_without_overwrite(tmp_path):
    import strattester.research.financial_offline_jobs as jobs
    job=sha256(b'job').hexdigest();payload={'prediction':.1}
    with patch.object(jobs.os,'rename',side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):jobs.publish_result(tmp_path,job,payload)
    assert jobs.publish_result(tmp_path,job,payload)['status']=='RECOVERED'
    assert len(list(tmp_path.iterdir()))==1

@pytest.mark.parametrize('stage',['before','after'])
def test_actual_abrupt_exit_publication_restart(tmp_path,stage):
    from strattester.research.financial_offline_jobs import publish_result
    job=sha256(b'job').hexdigest()
    code='''import os,sys
from strattester.research.financial_offline_jobs import publish_result
real=os.rename
def crash(source,target):
 if sys.argv[3]=='after':real(source,target)
 os._exit(77)
os.rename=crash
publish_result(sys.argv[1],sys.argv[2],{'prediction':.1})
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),job,stage],timeout=30,capture_output=True)
    assert result.returncode==77,result.stderr.decode(errors='replace')
    receipt=publish_result(tmp_path,job,{'prediction':.1})
    assert receipt['status']==('RECOVERED' if stage=='before' else 'REPLAY_VERIFIED')


def test_partial_stage_is_preserved_and_new_result_published(tmp_path):
    from strattester.research.financial_offline_jobs import publish_result
    job=sha256(b'job').hexdigest();partial=tmp_path/f'.stage-{job}-partial';partial.mkdir();(partial/'result.json').write_bytes(b'{')
    receipt=publish_result(tmp_path,job,{'prediction':.1})
    assert receipt['status']=='PUBLISHED' and (partial/'result.json').read_bytes()==b'{'
    assert str(partial) in receipt['preserved_stages']


def test_result_budget_precedes_serialization_of_unbounded_payload(tmp_path):
    from strattester.research.financial_offline_jobs import publish_result
    with pytest.raises(ValueError,match='budget'):publish_result(tmp_path,'a'*64,{'huge':'x'*100_000})
    assert not list(tmp_path.iterdir())


def test_concurrent_identical_jobs_publish_one_valid_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from strattester.research.financial_offline_jobs import publish_result
    job=sha256(b'concurrent').hexdigest();barrier=Barrier(2)
    def writer():
        barrier.wait(timeout=10)
        return publish_result(tmp_path,job,{'prediction':.1})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(writer) for _ in range(2)]
        receipts=[f.result(timeout=15) for f in futures]
    assert receipts[0]['sha256']==receipts[1]['sha256']
    assert Path(receipts[0]['path']).read_bytes()==Path(receipts[1]['path']).read_bytes()
    assert publish_result(tmp_path,job,{'prediction':.1})['status']=='REPLAY_VERIFIED'


def test_concurrent_conflicting_jobs_cannot_replace_completed_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from strattester.research.financial_offline_jobs import publish_result
    job=sha256(b'conflicting').hexdigest();barrier=Barrier(2)
    def writer(value):
        barrier.wait(timeout=10)
        try:return publish_result(tmp_path,job,{'prediction':value})
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(writer,value) for value in (.1,.2)]
        receipts=[f.result(timeout=15) for f in futures]
    assert sum(r is not None for r in receipts)==1
    completed=next(r for r in receipts if r is not None)
    assert sha256(Path(completed['path']).read_bytes()).hexdigest()==completed['sha256']
