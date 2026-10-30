"""Real-data adapter boundary contract ONLY; never grants synthetic or OOS acceptance."""
import re
EXPOSED_STAGE_E_NS=(1793293800000000000,1793380200000000000)
def assess_contract(request):
 required={'source_sha256','checkpoint_sha256','category','time_unit','train','validation','test','purge_ns','embargo_ns','samples','funding_status','slippage_status','historical_revisions','historical_availability'}
 if type(request) is not dict or set(request)!=required:raise ValueError('ADAPTER_SCHEMA')
 if request['category']!='linear' or request['time_unit']!='ns' or any(not re.fullmatch('[a-f0-9]{64}',str(request[k])) for k in ('source_sha256','checkpoint_sha256')):raise ValueError('ADAPTER_IDENTITY')
 spans=[]
 for name in ('train','validation','test'):
  span=request[name]
  if type(span) is not list or len(span)!=2 or any(type(x) is not int or x<0 for x in span) or span[0]>=span[1]:raise ValueError('ADAPTER_SPLIT')
  spans.append(span)
 for key in ('purge_ns','embargo_ns'):
  if type(request[key]) is not int or request[key]<0:raise ValueError('ADAPTER_GAP')
 if spans[0][1]+request['embargo_ns']>spans[1][0] or spans[1][1]+request['embargo_ns']>spans[2][0]:raise ValueError('OVERLAPPING_OR_UNEMBARGOED_SPLITS')
 if type(request['samples']) is not list or len(request['samples'])>1024:raise ValueError('ADAPTER_SAMPLE_BOUND')
 blockers=[]
 if spans[2][0]<EXPOSED_STAGE_E_NS[1] and spans[2][1]>EXPOSED_STAGE_E_NS[0]:blockers.append('EXPOSED_STAGE_E_NOT_NEW_OOS')
 for sample in request['samples']:
  if type(sample) is not dict or set(sample)!={'partition','origin_ns','feature_end_ns','label_end_ns','available_at_ns'}:raise ValueError('ADAPTER_SAMPLE_SCHEMA')
  partition=sample['partition']
  if partition not in ('train','validation','test') or any(type(sample[k]) is not int or sample[k]<0 for k in ('origin_ns','feature_end_ns','label_end_ns','available_at_ns')):raise ValueError('ADAPTER_SAMPLE_IDENTITY')
  origin=sample['origin_ns'];a,b=request[partition]
  if not a<=origin<b or sample['feature_end_ns']>origin or sample['available_at_ns']>origin or sample['label_end_ns']<=origin or sample['label_end_ns']>=b-request['purge_ns']:blockers.append('FUTURE_OR_OVERLAPPING_LABEL_AVAILABILITY')
 for k in ('funding_status','slippage_status','historical_revisions','historical_availability'):
  if request[k]!='INDEPENDENT_VERIFIER_REQUIRED':blockers.append(k.upper()+':MISSING_OR_UNPROVEN')
 return dict(status='CONTRACT_ONLY_REAL_OOS_BLOCKED',blockers=sorted(set(blockers)),qualification='NO_VERIFIER_OR_EXECUTION_AUTHORIZATION_IMPLEMENTED',synthetic_acceptance='UNCHANGED',real_oos='NOT_AUTHORIZED')
