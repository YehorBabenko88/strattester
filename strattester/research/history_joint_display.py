"""Bounded inert display export; no Math execution or qualification authority."""
import copy
from .grid_math_history import canonical, digest

LIMIT=8*1024*1024

def require(ok,code):
    if not ok:raise ValueError(code)

def receipt(p,key):
    require(type(p) is dict and p.get(key)==digest({k:v for k,v in p.items() if k!=key}),'DISPLAY_RECEIPT')

def joint_display_packet(history, request, result, expected_receipt, *, joint_published_at_ms):
    """Wrap original producer records. Publication is declared, never inferred.

    The display contract is deliberately unqualified until a separate hosted gate
    admits a source. Passing these consistency checks never changes runtime pins.
    """
    try:
        require(sum(len(canonical(p)) for p in (history,request,result))<=LIMIT,'DISPLAY_LIMIT')
        receipt(history,'handoff_sha256');receipt(result,'completion_receipt')
        require(result['completion_receipt']==expected_receipt,'DISPLAY_RECEIPT')
        require(history['schema']=='terminan.history.scientific-handoff.v1' and history['evidence_class']=='SYNTHETIC'
                and history['source_authenticity']=='UNATTESTED','DISPLAY_HISTORY')
        for p in (history,result):
            require(all(p.get(k) is False for k in ('execution_authority','training_authorized','trading_authorized')),'DISPLAY_AUTHORITY')
        require(request['schema']=='math.history.scientific.request.v1' and result['schema']=='math.history.scientific.result.v1'
                and result['api_revision']=='history-1.1+scientific-2.1','DISPLAY_SCHEMA')
        h=request['history'];provenance=result['provenance']
        require(result.get('joint_request',request)==request,'DISPLAY_CAPTURED_REQUEST')
        require(result['request_digest']==digest(request) and result['history']['request_digest']==digest(h),'DISPLAY_REQUEST')
        require(provenance=={k:h[k] for k in ('dataset_id','dataset_fingerprint','source','market','units','decision_ms','rows')},'DISPLAY_PROVENANCE')
        require(h['dataset_id']==history['dataset_id'] and h['dataset_fingerprint']==history['snapshot_fingerprint']
                and h['source']==history['source']['identity'] and h['market']==history['market']
                and h['units']['price']==history['units']['price'],'DISPLAY_SOURCE')
        require(result['history']['prefix_digest']==digest(h['rows']),'DISPLAY_PREFIX')
        prefix=[{'event_end_ms':r['event_end_ms'],'available_at_ms':r['available_at_ms'],
                 'watermark_ms':r['watermark_ms'],'value':r['close']} for r in h['rows']]
        require(prefix and history['observed_prices'][:len(prefix)]==prefix,'DISPLAY_PREFIX')
        d=h['decision_ms'];t=result['history']['forecast_target_event_end_ms']
        require(type(d) is int and type(t) is int and 0<=d<t<=2**53-1,'DISPLAY_CLOCK')
        require(type(joint_published_at_ms) is int and d<=joint_published_at_ms<=2**53-1,'DISPLAY_PUBLICATION')
        require(all(r['event_end_ms']<=r['watermark_ms']<=r['available_at_ms']<=d for r in h['rows']),'DISPLAY_CLOCK')
        require(any(p['decision_ms']==d and p['target_event_end_ms']==t and p['value']==result['history']['forecast']
                    and p['request_digest']==result['history']['request_digest']
                    and p['feature_event_end_ms']==result['history']['feature_event_end_ms']
                    and p['feature_available_at_ms']==result['history']['feature_available_at_ms'] for p in history['forecast_points']),'DISPLAY_FROZEN_FORECAST')
        require(all(result['math_source'][k]==history['model'][k] for k in ('commit','tree','python_sha256')),'DISPLAY_MATH_SOURCE')
        require(all(result['math_source']['manifest'].get(k)==v for k,v in history['model']['manifest'].items()),'DISPLAY_MATH_SOURCE')
        out={'schema':'terminan.unified-display.v1','contract_only':True,'qualification':'NOT_QUALIFIED',
             'evidence_class':'SYNTHETIC','source_authenticity':'UNATTESTED',
             'execution_authority':False,'training_authorized':False,'trading_authorized':False,
             'history':history,'joint_request':request,'joint_result':result,
             'joint_published_at_ms':joint_published_at_ms}
        out=copy.deepcopy(out);out['packet_sha256']=digest(out)
        require(len(canonical(out))<=LIMIT,'DISPLAY_LIMIT')
        return out
    except (KeyError,TypeError,OverflowError,RecursionError):
        raise ValueError('DISPLAY_INVALID') from None
