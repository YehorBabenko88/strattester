"""Consume Grid-assigned domain work on an operator-admitted scheduler.

No CLI, credentials, network grant, workspace creation or process launcher is
provided here. The Grid worker must supervise a dedicated process before this
seam is enabled remotely. Existing market writes are cache, not publication.
"""
import copy,re
from strattester.persistence.data_first_store import canonical

def need(ok):
 if not ok:raise ValueError('GRID_DATA_FIRST_REJECTED')

class _AssignedState:
 def __init__(self,scheduler,job,boundary):
  self.original=scheduler.state;self.job=copy.deepcopy(job);self.boundary=boundary
  self.row=dict(id=job['id'],payload=copy.deepcopy(job['payload']['domain']),state='DISCOVERED',progress={},result=None)
  prior=job.get('domain_state') or {};need(type(prior) is dict)
  self.sequence=prior.get('sequence',0);need(type(self.sequence) is int and 0<=self.sequence<2**63)
  self.lost=False;self.released=False
  if prior:
   status=prior.get('state');checkpoint=prior.get('checkpoint')
   need(status in ('SYNCING','PARTIAL','READY','RUNNING','YIELDED') and type(checkpoint) is dict and type(checkpoint.get('progress')) is dict)
   restored=checkpoint.get('state') if status=='YIELDED' else status
   need(restored in ('SYNCING','PARTIAL','READY','RUNNING'))
   self.row.update(state=restored,progress=copy.deepcopy(checkpoint['progress']),reason=checkpoint.get('reason',''))
 def instruments(self,categories):return self.original.instruments(categories)
 def get(self,key):
  need(key==self.job['id']);return copy.deepcopy(self.row)
 def _identity(self,key,owner,token):
  need(key==self.job['id'] and owner==self.job['lease_owner'] and token==self.job['lease_generation'])
  if self.lost or self.released:raise RuntimeError('Grid lease fenced or released')
 def claim(self,key,owner,now,lease_ms,max_active=None):
  self._identity(key,owner,self.job['lease_generation'])
  self.renew(key,owner,self.job['lease_generation'],now,lease_ms)
  if self.row['state']=='RUNNING':
   self.transition(key,owner,self.job['lease_generation'],now,'BLOCKED',reason='UNCERTAIN_EXECUTION_AFTER_LEASE',release=True)
   return None
  return self.job['lease_generation']
 def renew(self,key,owner,token,now,lease_ms):
  self._identity(key,owner,token)
  if self.boundary.renew(copy.deepcopy(self.job)) is not True:
   self.lost=True;raise RuntimeError('Grid lease fenced')
 def transition(self,key,owner,token,now,state,*,reason='',progress=None,result=None,release=False):
  self._identity(key,owner,token)
  checkpoint=copy.deepcopy(result if state=='COMPLETED' else dict(reason=reason,progress=self.row['progress'] if progress is None else progress))
  wire_state=state
  if release and state in ('PARTIAL','READY'):
   wire_state='YIELDED';checkpoint={'state':state,**checkpoint}
  canonical(checkpoint)
  ack=self.boundary.publish(copy.deepcopy(self.job),self.sequence+1,wire_state,checkpoint)
  if type(ack) is not dict or ack.get('accepted') is not True:
   self.lost=True;raise RuntimeError('Grid publication fenced')
  self.sequence+=1;self.row.update(state=state,reason=reason);self.released=release
  if progress is not None:self.row['progress']=copy.deepcopy(progress)
  if result is not None:self.row['result']=copy.deepcopy(result)

def execute_assigned(scheduler,job,lease_boundary,*,expected_source,cancel=lambda:False):
 """Synchronous fixed-domain operation; caller must own process supervision.

 `scheduler` must already have owner-admitted source/network/workspace factories.
 `expected_source` is an independent operator pin, never read from job metadata.
 Its equality check binds the request; it is not host/source authenticity proof.
 """
 need(type(expected_source) is str and re.fullmatch('[a-f0-9]{40}',expected_source))
 need(type(job) is dict and {'id','job_type','payload','lease_owner','lease_generation'}<=set(job))
 need(job['job_type']=='stratt_data_first_v1' and type(job['id']) is str and 1<=len(job['id'])<=128)
 need(type(job['lease_owner']) is str and 1<=len(job['lease_owner'])<=128 and type(job['lease_generation']) is int and job['lease_generation']>=1)
 p=job['payload'];need(type(p) is dict and set(p)=={'schema','source_commit','domain','resources'} and p['schema']=='grid.stratt-data-first.v1' and p['source_commit']==expected_source)
 d=p['domain'];need(type(d) is dict and set(d)=={'instrument','strategy_id','strategy_version','fingerprint','start_ms','end_ms','requirements','blockers','history_provenance','history_fingerprint','activity_basis'} and not d['blockers'])
 need(type(d['start_ms']) is int and type(d['end_ms']) is int and 0<=d['start_ms']<d['end_ms'])
 definition=scheduler._definition(d)
 need(scheduler._current_matches(d))
 plan=scheduler.planner.plan(definition,d['instrument'],start_ms=d['start_ms'],end_ms=d['end_ms'],now_ms=scheduler.clock_ms())
 need(not plan.blockers and plan.start_ms==d['start_ms'] and plan.end_exclusive_ms==d['end_ms'] and [r.json() for r in plan.requirements]==d['requirements'])
 if cancel():raise RuntimeError('Grid execution cancelled')
 state=_AssignedState(scheduler,job,lease_boundary)
 result=scheduler.process_assigned(state,job['id'],scheduler.monotonic()+scheduler.max_tick_seconds,owner=job['lease_owner'],cancel=lambda:bool(state.lost or cancel()))
 if state.lost:raise RuntimeError('Grid publication fenced')
 return result
