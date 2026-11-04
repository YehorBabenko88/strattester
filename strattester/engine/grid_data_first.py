"""Consume Grid-assigned domain work on an operator-admitted scheduler.

No CLI, credentials, network grant, workspace creation or process launcher is
provided here. The Grid worker must supervise a dedicated process before this
seam is enabled remotely. Existing market writes are cache, not publication.
"""
import copy,math,re
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

def validate_assigned(scheduler,job,*,expected_source):
 """Pure fixed request/registry/planner admission before discovery/domain I/O."""
 need(type(expected_source) is str and re.fullmatch('[a-f0-9]{40}',expected_source))
 need(type(job) is dict and {'id','job_type','payload','lease_owner','lease_generation'}<=set(job))
 need(job['job_type']=='stratt_data_first_v1' and type(job['id']) is str and 1<=len(job['id'])<=128)
 need(type(job['lease_owner']) is str and 1<=len(job['lease_owner'])<=128 and type(job['lease_generation']) is int and job['lease_generation']>=1)
 p=job['payload'];need(type(p) is dict and set(p)=={'schema','source_commit','domain','resources'} and p['schema']=='grid.stratt-data-first.v1' and p['source_commit']==expected_source)
 d=p['domain'];need(type(d) is dict and set(d)=={'instrument','strategy_id','strategy_version','fingerprint','start_ms','end_ms','requirements','blockers','history_provenance','history_fingerprint','activity_basis'} and d['blockers']==[])
 need(type(d['start_ms']) is int and type(d['end_ms']) is int and 0<=d['start_ms']<d['end_ms']<2**63)
 definition=scheduler._definition(d)
 plan=scheduler.planner.plan(definition,d['instrument'],start_ms=d['start_ms'],end_ms=d['end_ms'],now_ms=scheduler.clock_ms())
 need(not plan.blockers and plan.start_ms==d['start_ms'] and plan.end_exclusive_ms==d['end_ms'] and [r.json() for r in plan.requirements]==d['requirements'])
 need(set(job)<={'id','job_type','payload','lease_owner','lease_generation','lease_until','attempts','domain_state'})
 i=d['instrument'];r=p['resources']
 need(type(i) is dict and set(i)=={'category','symbol','status','launchTime','deliveryTime','fundingInterval','contractType','marketRegion','symbolId','baseCoin','quoteCoin'})
 need(i['category'] in scheduler.categories and type(i['symbol']) is str and re.fullmatch('[A-Z0-9_.-]{1,80}',i['symbol']))
 need(i['status'] in ('Trading','Closed','Settled','Delivering') and all(x is None or type(x) in (str,int) and len(str(x))<=128 for x in i.values()))
 need(type(d['requirements']) is list and 1<=len(d['requirements'])<=256)
 need(type(d['fingerprint']) is str and re.fullmatch('[a-f0-9]{64}',d['fingerprint']))
 for key in ('strategy_id','strategy_version'):need(type(d[key]) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}',d[key]))
 need(d['activity_basis'] in ('EXPLICIT_ARCHIVE_INTERVALS','LAUNCH_DELIVERY_BOUNDS_ONLY'))
 need(all(d[k] is None or type(d[k]) is str and re.fullmatch('[a-f0-9]{64}',d[k]) for k in ('history_provenance','history_fingerprint')))
 need((d['history_provenance'] is None)==(d['history_fingerprint'] is None) and (d['activity_basis']=='EXPLICIT_ARCHIVE_INTERVALS')==(d['history_provenance'] is not None))
 for q in d['requirements']:
  need(type(q) is dict and set(q)=={'symbol','dataset','timeframe','start_ms','end_ms','min_observations','required'})
  need(q['symbol']==i['symbol'] and type(q['required']) is bool and type(q['min_observations']) is int and 1<=q['min_observations']<=1000000)
  need(q['dataset'] in ('candles','mark_price','index_price','premium_index','open_interest','long_short_ratio') and type(q['timeframe']) is str and re.fullmatch('[1-9][0-9]*[mhdw]',q['timeframe']))
  need(type(q['start_ms']) is int and type(q['end_ms']) is int and 0<=q['start_ms']<=q['end_ms']<d['end_ms'])
 need(type(r) is dict and set(r)=={'cpu','ram_gb','scratch_gb','input_gb','gpu','data_locality'})
 need(all(type(r[k]) in (int,float) and math.isfinite(r[k]) and 0<=r[k]<=2**40 for k in ('cpu','ram_gb','scratch_gb','input_gb')) and r['gpu'] is False)
 need(r['data_locality'] is None or type(r['data_locality']) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,128}',r['data_locality']))
 canonical(p);_AssignedState(scheduler,job,None) # Pure prior-checkpoint grammar only.
 return d


def execute_assigned(scheduler,job,lease_boundary,*,expected_source,cancel=lambda:False):
 """Synchronous fixed-domain operation; caller must own process supervision.

 `scheduler` must already have owner-admitted source/network/workspace factories.
 `expected_source` is an independent operator pin, never read from job metadata.
 Its equality check binds the request; it is not host/source authenticity proof.
 """
 d=validate_assigned(scheduler,job,expected_source=expected_source)
 need(scheduler._current_matches(d))
 if cancel():raise RuntimeError('Grid execution cancelled')
 state=_AssignedState(scheduler,job,lease_boundary)
 result=scheduler.process_assigned(state,job['id'],scheduler.monotonic()+scheduler.max_tick_seconds,owner=job['lease_owner'],cancel=lambda:bool(state.lost or cancel()))
 if state.lost:raise RuntimeError('Grid publication fenced')
 return result
