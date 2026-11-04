"""Fixed child protocol with a preconstructed fixture scheduler; no deployment claim."""
import pytest
import copy,hashlib,io,json,subprocess,sys
from pathlib import Path
from tests.engine.test_data_first_scheduler import setup,no_actual_network
from strattester.engine.grid_data_first_worker import serve

SCHEMA='grid.data-first.process.v1'
def frame(nonce,seq,op,body):return json.dumps(dict(schema=SCHEMA,nonce=nonce,seq=seq,op=op,body=body),sort_keys=True,separators=(',',':')).encode()+b'\n'
class Pipe:
 def __init__(self,job,*,bad_nonce=False):self.job=job;self.nonce='a'*64;self.pending=[frame(self.nonce,0,'INIT',{'job':job})];self.written=[];self.bad_nonce=bad_nonce
 def readline(self,limit):return self.pending.pop(0)[:limit] if self.pending else b''
 def write(self,raw):
  item=json.loads(raw);self.written.append(item);op=item['op'];body=item['body']
  if op=='RENEW':value={'valid':True}
  elif op=='CHECKPOINT':value=dict(accepted=True,state=body['state'],sha256=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest(),request_sha256=hashlib.sha256(json.dumps(self.job['payload'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
  else:return len(raw)
  self.pending.append(frame('b'*64 if self.bad_nonce else self.nonce,item['seq'],'ACK',{'op':op,'value':value}));return len(raw)
 def flush(self):pass

def job_for(scheduler,state):
 scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 return dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node',lease_generation=1)

def test_admitted_scheduler_consumes_real_sqlite_sync_via_only_closed_rpc(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.max_pages=10;job=job_for(scheduler,state);pipe=Pipe(job)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==0
 assert pipe.written[-1]['op']=='DONE' and pipe.written[-1]['body']['state']=='COMPLETED'
 assert [p['end'] for url,p in calls if url.endswith('kline')]==[120000,60000,0]
 assert state.get(job['id'])['state']=='DISCOVERED'

def test_wrong_nonce_ack_and_missing_source_do_not_download_or_echo_details(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);job=job_for(scheduler,state);before=len(calls);pipe=Pipe(job,bad_nonce=True)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==78
 assert len(calls)==before and pipe.written[-1]['op']=='ERROR'
 pipe=Pipe(job);assert serve(scheduler,None,input_stream=pipe,output_stream=pipe)==78
 assert len(calls)==before

def test_fixed_main_blocks_factory_provisioning_without_any_app_import(tmp_path):
 entry=Path(__file__).resolve().parents[2]/'strattester/engine/grid_data_first_worker.py'
 job=dict(id='fixture',job_type='stratt_data_first_v1',payload={})
 child=subprocess.run([sys.executable,'-I','-S','-B',str(entry)],input=frame('a'*64,0,'INIT',{'job':job}),capture_output=True,timeout=10)
 assert child.returncode==78 and child.stderr==b''
 assert json.loads(child.stdout)['body']=={'code':'PROCESS_PROVISIONING_NOT_IMPLEMENTED'}


def test_numeric_true_ack_is_rejected_before_sync(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);job=job_for(scheduler,state);before=len(calls)
 class Numeric(Pipe):
  def write(self,raw):
   n=super().write(raw)
   if json.loads(raw)['op']=='RENEW':
    reply=json.loads(self.pending[-1]);reply['body']['value']={'valid':1};self.pending[-1]=json.dumps(reply,sort_keys=True,separators=(',',':')).encode()+b'\n'
   return n
 pipe=Numeric(job)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==78
 assert len(calls)==before and pipe.written[-1]['body']=={'code':'PROCESS_LEASE_FENCED'}


def test_three_worker_sessions_preserve_server_sequence_and_cached_pages(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);job=job_for(scheduler,state)
 for generation in (1,2,3):
  job['lease_generation']=generation;pipe=Pipe(copy.deepcopy(job))
  assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==0
  assert pipe.written[-1]['body']['state']==('COMPLETED' if generation==3 else 'YIELDED')
  last=next(item['body'] for item in reversed(pipe.written) if item['op']=='CHECKPOINT')
  job['domain_state']={**last,'sha256':hashlib.sha256(json.dumps(last,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 assert [p['end'] for url,p in calls if url.endswith('kline')]==[120000,60000,0]
 assert state.get(job['id'])['state']=='DISCOVERED'

def test_private_application_exception_never_becomes_child_diagnostic(tmp_path,monkeypatch):
 scheduler,state,*_=setup(tmp_path);job=job_for(scheduler,state);pipe=Pipe(job)
 def fail(*args):raise ValueError('SECRET_CREDENTIAL')
 monkeypatch.setattr(scheduler,'_definition',fail)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==78
 assert pipe.written[-1]['body']=={'code':'PROCESS_CHILD_FAILED'}
 assert 'SECRET' not in json.dumps(pipe.written)


@pytest.mark.parametrize('mutation',[lambda j:j['payload'].update(source_commit='b'*40),lambda j:j['payload']['domain'].update(unexpected=True),lambda j:j['payload']['domain']['instrument'].update(category='inverse'),lambda j:j['payload']['resources'].update(cpu=-1)])
def test_invalid_assigned_request_has_no_prepare_or_domain_io(tmp_path,mutation,monkeypatch):
 scheduler,state,calls,*_=setup(tmp_path);job=job_for(scheduler,state);effects=[];mutation(job)
 scheduler.protected_prepare=lambda:effects.append('DISCOVERY_EFFECT')
 scheduler.protected_expected_source='a'*40
 before=len(calls)
 def forbidden(*a,**kw):raise AssertionError('SQLITE_READ_BEFORE_ADMISSION')
 monkeypatch.setattr(state,'instruments',forbidden)
 pipe=Pipe(job)
 assert serve(scheduler,'a'*40,input_stream=pipe,output_stream=pipe)==78
 assert effects==[] and len(calls)==before
 assert all(row['op'] not in ('RENEW','CHECKPOINT') for row in pipe.written)
