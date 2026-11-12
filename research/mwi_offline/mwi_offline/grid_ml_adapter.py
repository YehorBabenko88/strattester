"""Pure local Grid ML preparation metadata; no owner calls or permission grants."""
import copy
import math
import re
import uuid

AUDITED_GRID_HEAD='9c6113421024777a988ba69bf2dd1f79bd712130'
KEYS={'schema','observed_grid_head','market_content_dataset_id','feature_cohort_id','feature_version','native_dataset_uuid','native_dataset_hash','evidence_class','knowledge_cutoff_ms','sample_count','task','model_family','search_space','resources'}
SEARCH={'target_key','objective','n_estimators','max_depth','learning_rate'}
RESOURCES={'threads','timeout_seconds','ram_limit_mb','cpu','ram_gb','scratch_gb','gpu'}

def need(ok,message):
 if not ok:raise ValueError(message)
def hexpin(value,n):need(type(value) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',value) is not None,'IDENTITY_PIN')
def number(value,lo,hi,integer=False):
 need(type(value) is int if integer else type(value) in (int,float),'NUMERIC_TYPE')
 need(lo<=value<=hi and math.isfinite(value),'NUMERIC_BUDGET')
def token(value):need(type(value) is str and re.fullmatch('[A-Za-z0-9_.-]{1,64}',value) is not None,'IDENTITY_TOKEN')

def prepare_request(request):
 """Return bounded owned DATA_ONLY metadata; unaccepted native interface blocks all calls.

 Native UUID/hash are caller declarations only, never provisioned by this function.
 The inspected Grid source is a pin for audit, not an accepted implementation grant.
 """
 need(type(request) is dict and all(type(k) is str for k in request) and set(request)==KEYS,'REQUEST_SCHEMA')
 q=request
 need(type(q['schema']) is str and q['schema']=='mwi.local.grid-ml-preparation.request.v1','REQUEST_SCHEMA')
 hexpin(q['observed_grid_head'],40);need(q['observed_grid_head']==AUDITED_GRID_HEAD,'UNAUDITED_GRID_SOURCE')
 for key in ('market_content_dataset_id','feature_cohort_id'):hexpin(q[key],64)
 token(q['feature_version']);token(q['model_family'])
 need(type(q['evidence_class']) is str and q['evidence_class']=='SYNTHETIC','HISTORICAL_AUTHENTICITY_NOT_PROVISIONED')
 number(q['knowledge_cutoff_ms'],0,2**53-1,True);number(q['sample_count'],1,256,True)
 need(type(q['task']) is str and q['task'] in ('binary','regression'),'UNSUPPORTED_NATIVE_TASK')
 native=q['native_dataset_uuid'];native_hash=q['native_dataset_hash']
 need((native is None)==(native_hash is None),'NATIVE_MAPPING_PAIR')
 if native is not None:
  need(type(native) is str and len(native)==36,'NATIVE_UUID_REQUIRED')
  try:need(str(uuid.UUID(native))==native,'CANONICAL_NATIVE_UUID')
  except (ValueError,AttributeError):raise ValueError('CANONICAL_NATIVE_UUID') from None
  hexpin(native_hash,64)
 space=q['search_space'];need(type(space) is dict and all(type(k) is str for k in space) and set(space)==SEARCH,'SEARCH_SCHEMA')
 # Only inspect builtin list lengths; never consume caller iterators or expand products.
 product=1
 for name in sorted(SEARCH):
  axis=space[name];need(type(axis) is list and 1<=len(axis)<=32,'SEARCH_AXIS_BUDGET')
  product*=len(axis)
  need(product<=4,'SEARCH_PRODUCT_BUDGET')
 for name,axis in space.items():
  for value in axis:
   if name=='target_key':token(value)
   elif name=='objective':need(type(value) is str and value==q['task'],'TASK_OBJECTIVE_MISMATCH')
   elif name=='n_estimators':number(value,1,32,True)
   elif name=='max_depth':number(value,1,3,True)
   else:number(value,.001,.1)
 # Duplicate axis members obscure logical experiment identity; reject them.
 for axis in space.values():need(len({(type(v).__name__,v) for v in axis})==len(axis),'DUPLICATE_SEARCH_VALUE')
 r=q['resources'];need(type(r) is dict and all(type(k) is str for k in r) and set(r)==RESOURCES,'RESOURCE_SCHEMA')
 for key,lo,hi,integer in (('threads',1,1,True),('timeout_seconds',1,60,True),('ram_limit_mb',128,512,True),('cpu',1,1,False),('ram_gb',.125,.5,False),('scratch_gb',0,.1,False)):
  number(r[key],lo,hi,integer)
 need(r['gpu'] is False,'GPU_REFUSED')
 need(r['ram_gb']*1024>=r['ram_limit_mb'],'INCONSISTENT_RAM_REQUEST')
 blockers=['OWNER_INTERFACE_NOT_ACCEPTED','TIMESTAMP_ROUNDTRIP_NOT_QUALIFIED','RESOURCE_PAYLOAD_COMPOSITION_NOT_ACCEPTED','RESEARCH_REGISTRY_LIFECYCLE_NOT_AGREED']
 if native is None:blockers.append('NATIVE_DATASET_MAPPING_NOT_PROVISIONED')
 else:blockers.append('NATIVE_DATASET_MAPPING_NOT_VERIFIED')
 out=dict(schema='mwi.local.grid-ml-preparation.v1',status='BLOCKED',mode='PREPARATION_ONLY',
  source=dict(observed_grid_head=AUDITED_GRID_HEAD,accepted_grid_head=None,interface_accepted=False),
  dataset={key:q[key] for key in ('market_content_dataset_id','feature_cohort_id','feature_version','native_dataset_uuid','native_dataset_hash','evidence_class','knowledge_cutoff_ms','sample_count')},
  intended_owner_symbol='grid.ml_experiment_factory.create_experiment_jobs',
  native_arguments_if_owner_admits=dict(dataset_id=native,model_family=q['model_family'],search_space=space,limit=product),
  resource_request=r,combination_count=product,task=q['task'],blockers=blockers,
  submit_allowed=False,training_allowed=False,promotion_allowed=False,
  native_effects='NONE_NOT_INVOKED',source_authenticity='NOT_EVALUATED',
  task_scope='NATIVE_BINARY_OR_REGRESSION_ONLY_NOT_MWI_THREE_CLASS',
  quotas_scope='PROPOSAL_NOT_OPERATOR_ADMISSION',checkpoint_scope='OWNER_RETRY_IS_NOT_OPTIMIZER_RESUME')
 out['dataset']['native_mapping_status']='MISSING' if native is None else 'CALLER_DECLARED_NOT_VERIFIED'
 return copy.deepcopy(out)
