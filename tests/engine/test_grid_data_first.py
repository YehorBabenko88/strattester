"""Consumed external lease path: real SyncEngine and SQLite, no sockets."""
import copy
import pytest
from tests.engine.test_data_first_scheduler import setup,no_actual_network
from strattester.engine.grid_data_first import execute_assigned

class Lease:
 def __init__(self):self.events=[];self.alive=True
 def renew(self,job):return self.alive
 def publish(self,job,sequence,state,checkpoint):
  if not self.alive:return None
  self.events.append((sequence,state,copy.deepcopy(checkpoint)))
  return {'accepted':True}

def test_existing_sync_execution_uses_grid_fence_and_never_local_claim(tmp_path,monkeypatch):
 scheduler,state,calls,registry,stores=setup(tmp_path)
 scheduler.max_pages=10;scheduler.discover();keys=scheduler.plan(start_ms=0,end_ms=180000)
 local=state.get(keys[0]);domain=copy.deepcopy(local['payload']);domain['blockers']=list(domain['blockers'])
 def forbidden(*a,**k):raise AssertionError('SECOND_LEASE_AUTHORITY')
 monkeypatch.setattr(state,'claim',forbidden);monkeypatch.setattr(state,'transition',forbidden)
 lease=Lease();job=dict(id=keys[0],job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=domain,resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=7)
 result=execute_assigned(scheduler,job,lease,expected_source='a'*40)
 assert result['state']=='COMPLETED'
 assert result['result']['output']=={'count':3,'symbol':'ALPHAUSDT'}
 assert state.get(keys[0])['state']=='DISCOVERED'
 assert lease.events[-1][1]=='COMPLETED'
 assert [e[0] for e in lease.events]==list(range(1,len(lease.events)+1))
 assert len([u for u,p in calls if u.endswith('kline')])==3

def test_missing_source_or_lost_grid_lease_cannot_start_download(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=7)
 before=len(calls)
 with pytest.raises(ValueError):execute_assigned(scheduler,job,Lease(),expected_source=None)
 lease=Lease();lease.alive=False
 with pytest.raises(RuntimeError):execute_assigned(scheduler,job,lease,expected_source='a'*40)
 assert len(calls)==before


def test_final_publication_loss_does_not_publish_locally(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.max_pages=10;scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 class RejectFinal(Lease):
  def publish(self,job,sequence,status,checkpoint):
   if status=='COMPLETED':self.alive=False;return None
   return super().publish(job,sequence,status,checkpoint)
 lease=RejectFinal();job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=7)
 with pytest.raises(RuntimeError):execute_assigned(scheduler,job,lease,expected_source='a'*40)
 assert state.get(key)['state']=='DISCOVERED' and state.get(key)['result'] is None
 assert not any(e[1]=='COMPLETED' for e in lease.events)

def test_cancelled_assignment_cannot_download_or_publish(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 lease=Lease();job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=7)
 before=len(calls)
 with pytest.raises(RuntimeError):execute_assigned(scheduler,job,lease,expected_source='a'*40,cancel=lambda:True)
 assert len(calls)==before and lease.events==[]


def test_external_requirements_must_match_existing_history_planner_before_io(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 domain=copy.deepcopy(state.get(key)['payload']);domain['requirements'][0]['start_ms']=60000
 job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=domain,resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=7)
 before=len(calls)
 with pytest.raises(ValueError):execute_assigned(scheduler,job,Lease(),expected_source='a'*40)
 assert len(calls)==before


def test_three_page_backfill_yields_then_resumes_without_local_claim(tmp_path,monkeypatch):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 def forbidden(*a,**k):raise AssertionError('SECOND_LEASE_AUTHORITY')
 monkeypatch.setattr(state,'claim',forbidden);monkeypatch.setattr(state,'transition',forbidden)
 class Authority(Lease):
  def __init__(self):super().__init__();self.saved=None
  def publish(self,job,sequence,status,checkpoint):
   ack=super().publish(job,sequence,status,checkpoint)
   self.saved=dict(sequence=sequence,state=status,checkpoint=copy.deepcopy(checkpoint))
   if status=='YIELDED':self.alive=False
   return ack
 boundary=Authority();restored=[];original=scheduler.process_assigned
 def capture(external,key,deadline,**kwargs):
  restored.append(external.get(key));return original(external,key,deadline,**kwargs)
 monkeypatch.setattr(scheduler,'process_assigned',capture)
 for generation in (1,2,3):
  boundary.alive=True
  job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=generation,domain_state=copy.deepcopy(boundary.saved))
  result=execute_assigned(scheduler,job,boundary,expected_source='a'*40)
  if generation<3:
   assert result['state']=='PARTIAL' and boundary.saved['state']=='YIELDED' and not boundary.alive
  else:assert result['state']=='COMPLETED' and result['result']['output']=={'count':3,'symbol':'ALPHAUSDT'}
 assert restored[0]['state']=='DISCOVERED'
 assert all(row['state']=='PARTIAL' and 'last_page' in row['progress'] for row in restored[1:])
 assert [p['end'] for u,p in calls if u.endswith('kline')]==[120000,60000,0]
 assert state.get(key)['state']=='DISCOVERED' and state.get(key)['result'] is None
 assert [e[0] for e in boundary.events]==list(range(1,len(boundary.events)+1))


def test_ready_resource_block_yields_and_resumes_without_new_download(tmp_path):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.max_pages=10;scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 class SavedLease(Lease):
  saved=None
  def publish(self,job,sequence,status,checkpoint):
   ack=super().publish(job,sequence,status,checkpoint)
   self.saved=dict(sequence=sequence,state=status,checkpoint=copy.deepcopy(checkpoint));return ack
 boundary=SavedLease();job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=1)
 scheduler.resource_admission=lambda:False
 result=execute_assigned(scheduler,job,boundary,expected_source='a'*40)
 assert result['state']=='READY' and boundary.saved['state']=='YIELDED'
 assert boundary.saved['checkpoint']['state']=='READY' and boundary.saved['checkpoint']['reason']=='RESOURCE_ADMISSION_BLOCKED'
 before=len(calls);job['domain_state']=copy.deepcopy(boundary.saved);job['lease_generation']=2;scheduler.resource_admission=lambda:True
 result=execute_assigned(scheduler,job,boundary,expected_source='a'*40)
 assert result['state']=='COMPLETED' and len(calls)==before
 assert state.get(key)['state']=='DISCOVERED'

def test_uncertain_prior_execution_is_blocked_not_reexecuted(tmp_path,monkeypatch):
 scheduler,state,calls,*_=setup(tmp_path);scheduler.discover();key=scheduler.plan(start_ms=0,end_ms=180000)[0]
 def forbidden(*a,**k):raise AssertionError('SECOND_LEASE_AUTHORITY')
 monkeypatch.setattr(state,'claim',forbidden);monkeypatch.setattr(state,'transition',forbidden)
 job=dict(id=key,job_type='stratt_data_first_v1',payload=dict(schema='grid.stratt-data-first.v1',source_commit='a'*40,domain=state.get(key)['payload'],resources=dict(cpu=1.,ram_gb=1.,scratch_gb=1.,input_gb=0.,gpu=False,data_locality=None)),lease_owner='node1',lease_generation=2,domain_state=dict(sequence=3,state='RUNNING',checkpoint={'reason':'','progress':{'input_sha256':'c'*64}}))
 before=len(calls);boundary=Lease();result=execute_assigned(scheduler,job,boundary,expected_source='a'*40)
 assert result['state']=='BLOCKED' and result['reason']=='UNCERTAIN_EXECUTION_AFTER_LEASE'
 assert len(calls)==before and boundary.events==[(4,'BLOCKED',{'reason':'UNCERTAIN_EXECUTION_AFTER_LEASE','progress':{'input_sha256':'c'*64}})]
