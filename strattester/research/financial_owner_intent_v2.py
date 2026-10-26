"""Canonical native-compatible owner intent. No signature alone authorizes G1."""
import re
from .financial_contract import digest,integer
from .financial_snapshot import canonical_bytes

DOMAIN=b'STRATTESTER_PHYSICAL_G1_OWNER_V2\0'
FIELDS=frozenset(('version','purpose','owner_id','key_id','target_sha','tree_sha','binary_sha256','package_sha256','vm_identity_sha256','input_hashes','issued_at_ns','expires_at_ns','nonce','operations','limits'))
CAPS=dict(cpu_percent=10,memory_bytes=2*1024**3,wall_seconds=60,output_bytes=64*1024**2,max_processes=1)

def canonical_owner_intent(value,*,now_ns):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('owner v2 schema')
    if type(value['version']) is not int or value['version']!=2 or value['purpose']!='PHYSICAL_G1_AUTHORIZATION':raise ValueError('owner v2 purpose/version')
    for field in ('owner_id','key_id'):
        if type(value[field]) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value[field]):raise ValueError('ASCII owner identity')
    for name,size in (('target_sha',40),('tree_sha',40),('binary_sha256',64),('package_sha256',64),('vm_identity_sha256',64),('nonce',64)):
        digest(value[name],size)
    inputs=value['input_hashes']
    if type(inputs) is not dict or not 1<=len(inputs)<=64:raise ValueError('owner input budget')
    for name,sha in inputs.items():
        if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',name):raise ValueError('logical input name')
        digest(sha)
    for t in (now_ns,value['issued_at_ns'],value['expires_at_ns']):
        integer(t,'owner time',1)
        if t>2**63-1:raise ValueError('native integer range')
    if not value['issued_at_ns']<=now_ns<=value['expires_at_ns'] or value['expires_at_ns']-value['issued_at_ns']>600_000_000_000:raise ValueError('expired/future owner intent')
    if value['operations']!=['synthetic_cpu_inference']:raise ValueError('owner operation')
    limits=value['limits']
    if type(limits) is not dict or set(limits)!=set(CAPS):raise ValueError('owner limit schema')
    for name,cap in CAPS.items():
        integer(limits[name],name,1)
        if limits[name]>cap:raise ValueError('owner resource ceiling')
    result=canonical_bytes(value)
    if len(result)>65536:raise ValueError('owner intent byte budget')
    return result
