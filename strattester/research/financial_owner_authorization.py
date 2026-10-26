"""External owner-signed G1 intent. Signature never replaces native isolation.

The completed authorization is EXTERNAL to the immutable test ZIP: placing a
package hash inside that package's signed plan would create a hash cycle.
No owner private key is collected, generated or shipped by this module.
"""
from .financial_contract import digest,integer
from .financial_snapshot import verified_bytes,bounded_json,canonical_bytes
from .financial_signatures import OpenSSLVerifier,load_trust_store

AUTHORIZATION_DOMAIN=b'STRATTESTER_PHYSICAL_G1_OWNER_V1\x00'
# This RFC8032 key's private seed ships with the public producer fixture.
# An externally pinned trust store cannot make that disclosed key secret;
# aliases must not promote the fixture into an owner authorization identity.
PUBLIC_FIXTURE_KEYS=frozenset({bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')})


def verify_owner_authorization(plan_path,*,plan_sha256,signature_path,signature_sha256,
        trust_store_path,trust_store_sha256,owner_id,verifier,now_ns,expected_target_sha,
        expected_tree_sha,expected_binary_sha256,expected_package_sha256,expected_node_identity):
    integer(now_ns,'independent verification time',1)
    if type(verifier) is not OpenSSLVerifier:raise ValueError('independent pinned verifier required')
    p=bounded_json(verified_bytes(plan_path,plan_sha256,64*1024))
    required={'version','purpose','owner_id','key_id','target_sha','tree_sha','binary_sha256','package_sha256','node_identity_sha256','issued_at_ns','expires_at_ns','nonce','operations','limits'}
    if set(p)!=required or type(p['version']) is not int or p['version']!=1 or p['purpose']!='PHYSICAL_G1_AUTHORIZATION':raise ValueError('owner plan schema/purpose')
    for name in ('owner_id','key_id'):
        if type(p[name]) is not str or not 1<=len(p[name])<=128:raise ValueError('owner identity')
    if p['owner_id']!=owner_id:raise ValueError('owner scope mismatch')
    for name,expected,length in [('target_sha',expected_target_sha,40),('tree_sha',expected_tree_sha,40),('binary_sha256',expected_binary_sha256,64),('package_sha256',expected_package_sha256,64),('node_identity_sha256',expected_node_identity,64)]:
        digest(expected,length);digest(p[name],length)
        if p[name]!=expected:raise ValueError('owner plan '+name+' mismatch')
    integer(p['issued_at_ns'],'issued',1);integer(p['expires_at_ns'],'expires',1);digest(p['nonce'])
    if not p['issued_at_ns']<=now_ns<=p['expires_at_ns'] or p['expires_at_ns']-p['issued_at_ns']>600_000_000_000:raise ValueError('expired/future/overlong owner plan')
    if p['operations']!=['synthetic_cpu_inference']:raise ValueError('owner operation scope')
    caps={'cpu_percent':10,'memory_bytes':2*1024**3,'wall_seconds':60,'output_bytes':64*1024**2,'max_processes':1}
    if type(p['limits']) is not dict or set(p['limits'])!=set(caps):raise ValueError('owner resource schema')
    for name,maximum in caps.items():
        integer(p['limits'][name],name,1)
        if p['limits'][name]>maximum:raise ValueError('owner resource ceiling')
    trust=load_trust_store(trust_store_path,trust_store_sha256)
    key=trust.key(owner_id,p['key_id'],p['issued_at_ns']);trust.key(owner_id,p['key_id'],now_ns)
    if key in PUBLIC_FIXTURE_KEYS:raise ValueError('public fixture key cannot authorize an owner')
    signature=verified_bytes(signature_path,signature_sha256,64)
    verifier.verify(key,AUTHORIZATION_DOMAIN+canonical_bytes(p),signature)
    # No nonce is consumed and no process is started here. Actual execution
    # must additionally verify independent native receipts, claim a one-shot
    # nonce atomically, and enforce every requested control BEFORE creation.
    return {'authorization_signature_verified':True,'plan_sha256':plan_sha256,'signature_sha256':signature_sha256,
            'owner_id':owner_id,'nonce':p['nonce'],'limits':p['limits'],'physical_g1':'NOT_AUTHORIZED',
            'native_enforcement':'INDEPENDENT_PROOF_REQUIRED','nonce_consumed':False,'process_created':False}
