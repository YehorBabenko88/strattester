"""Grid v1.1 content/clock contract. Source trust pins are provisioned externally."""
import hashlib
import json

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def pin(v,n=64):return isinstance(v,str) and len(v)==n and all(c in '0123456789abcdef' for c in v)
def clock(v):return type(v) is int and 0<=v<=2**53-1

def validate_timed_envelope(d):
    try:
        source=d['source'];q=d['request'];rows=d['rows']
        if set(source)!={'identity','source_revision','epoch'} or not pin(source['source_revision'],40):raise ValueError('SOURCE_IDENTITY')
        if any(not isinstance(source[k],str) or not source[k] for k in ('identity','epoch')):raise ValueError('SOURCE_IDENTITY')
        if not pin(d['dataset_id']) or not clock(d['watermark_ms']):raise ValueError('DATASET_ID')
        for i,r in enumerate(rows):
            if not all(clock(r[k]) for k in ('event_start_ms','event_end_ms','source_event_start_ms','source_event_end_ms','watermark_ms','available_at_ms')):raise ValueError('ROW_CLOCK')
            if not r['event_start_ms']<=r['source_event_start_ms']<=r['source_event_end_ms']<r['event_end_ms']:raise ValueError('SOURCE_EVENT_CLOCK')
            if not r['event_end_ms']<=r['watermark_ms']<=r['available_at_ms']<=q['as_of_ms']:raise ValueError('WATERMARK_OR_AVAILABILITY')
            if (not pin(r['revision']) or not pin(r['source_receipt_hash']) or r['source_receipt_hash']!=d['source_receipts'][i]):raise ValueError('SOURCE_RECEIPT')
        if d['watermark_ms']!=max(r['watermark_ms'] for r in rows):raise ValueError('WATERMARK')
        content={'schema':'grid.dataset.v1.1','source':source,'identity':{k:q[k] for k in ('venue','market_type','symbol','units')},
            'timeframe':'1m','representation':'historical_aggregate','evidence_class':d['evidence_class'],
            'rows':rows,'source_receipts':d['source_receipts']}
        if digest(content)!=d['dataset_id']:raise ValueError('DATASET_ID')
    except (KeyError,TypeError,OverflowError) as exc:raise ValueError('TIMED_ADMISSION_UNAVAILABLE') from exc
