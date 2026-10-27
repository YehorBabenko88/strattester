"""Independent executable conformance examples for GRID_EXPORT_SPEC.md.

Test-side reference validator only: not a native exporter or deployment trust store.
"""
from copy import deepcopy
import hashlib
import hmac
import json
import pytest

KEY=b'test-only-producer-key-not-a-deployment-credential'

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def signed_manifest():
    source=dict(source_id='sqlite:fixture',epoch='epoch-1',schema_sha256='a'*64,
                snapshot_id='transaction-1',revision_history=True,first_availability=True,
                event_watermark_ns=100,availability_watermark_ns=100,complete=True,
                artifact_sha256=hashlib.sha256(b'fixture').hexdigest(),artifact_bytes=7,row_count=1)
    body=dict(version=1,producer='fixture-producer',key_id='fixture-key',epoch='epoch-1',
              cutoff_ns=100,sources=[source],quality='VERIFIED',eligible=True)
    return body,hmac.digest(KEY,canonical(body),'sha256').hex()

def verify(body,signature,artifacts):
    if not hmac.compare_digest(hmac.digest(KEY,canonical(body),'sha256').hex(),signature):raise ValueError('signature')
    if body['version']!=1 or type(body['version']) is not int:raise ValueError('version')
    if body['producer']!='fixture-producer' or body['key_id']!='fixture-key':raise ValueError('trust identity')
    if body['epoch']!='epoch-1' or body['cutoff_ns']!=100:raise ValueError('replayed cut')
    if body['quality']!='VERIFIED' or body['eligible'] is not True:raise ValueError('quality')
    sources=body['sources']
    if len(sources)!=1 or {s['source_id'] for s in sources}!={'sqlite:fixture'}:raise ValueError('source membership')
    for s in sources:
        if s['epoch']!=body['epoch'] or s['schema_sha256']!='a'*64 or not s['snapshot_id']:raise ValueError('source identity')
        if any(s[k] is not True for k in ('revision_history','first_availability','complete')):raise ValueError('missing facts')
        if any(type(s[k]) is not int or s[k]<body['cutoff_ns'] for k in ('event_watermark_ns','availability_watermark_ns')):raise ValueError('incomplete cut')
        data=artifacts[s['source_id']]
        if len(data)!=s['artifact_bytes'] or hashlib.sha256(data).hexdigest()!=s['artifact_sha256']:raise ValueError('bytes binding')
    return True


def test_signed_exact_cut_reference_accepts():
    body,sig=signed_manifest();assert verify(body,sig,{'sqlite:fixture':b'fixture'})

@pytest.mark.parametrize('field,value', [('epoch','other'),('schema_sha256','b'*64),
    ('snapshot_id',''),('revision_history',False),('first_availability',False),
    ('event_watermark_ns',99),('availability_watermark_ns',99),('complete',False),
    ('artifact_sha256','c'*64),('artifact_bytes',8)])
def test_even_signed_missing_or_incoherent_source_facts_reject(field,value):
    body,_=signed_manifest();body['sources'][0][field]=value
    sig=hmac.digest(KEY,canonical(body),'sha256').hex()
    with pytest.raises(ValueError):verify(body,sig,{'sqlite:fixture':b'fixture'})


def test_forged_producer_or_hash_cannot_authorize_export():
    body,sig=signed_manifest();body['producer']='attacker'
    with pytest.raises(ValueError):verify(body,sig,{'sqlite:fixture':b'fixture'})

@pytest.mark.parametrize('sources',[[], ['duplicate']])
def test_partial_or_duplicate_source_set_reject(sources):
    body,_=signed_manifest();body['sources']=[] if not sources else body['sources']*2
    sig=hmac.digest(KEY,canonical(body),'sha256').hex()
    with pytest.raises(ValueError):verify(body,sig,{'sqlite:fixture':b'fixture'})
