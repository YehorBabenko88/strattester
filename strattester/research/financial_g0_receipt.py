"""Verify two G0 binding signatures against external pins; never admit a target.

Reads only pinned receipt/policy/trust bytes. Does not collect facts, dereference
receipt hashes, open authorized paths, claim snapshot isolation or publish nonces.
"""
from hashlib import sha256

from .financial_contract import digest, integer
from .financial_executable_inventory import _local_path
from .financial_g0_evidence import _exact
from .financial_signatures import load_trust_store, decode64, PUBLIC_SOFTWARE_FIXTURE_KEYS, OpenSSLVerifier
from .financial_snapshot import bounded_json, canonical_bytes, verified_bytes

DOMAIN = b'STRATTESTER_G0_TARGET_BINDING_V1\x00'
BINDING_FIELDS = (
    'source_sha', 'tree_sha', 'package_sha256', 'command_manifest_sha256',
    'vm_identity_sha256', 'provider_identity_sha256', 'sandbox_root_sha256',
    'evidence_root_sha256', 'snapshot_generation_sha256', 'rollback_receipt_sha256',
    'private_delivery_receipt_sha256', 'capture_controls_receipt_sha256',
    'acl_scope_receipt_sha256', 'tool_roster_sha256', 'evidence_manifest_sha256',
)
ROLE_FIELDS = ('owner_id', 'provider_id', 'owner_key_id', 'provider_key_id')


def verify_g0_receipt(*, manifest_path, manifest_sha256, policy_path, policy_sha256,
                      trust_store_path, trust_store_sha256, verifier, now_ns):
    # Callbacks/subclasses can attest forged bytes without checking Ed25519.
    if type(verifier) is not OpenSSLVerifier:
        raise ValueError('independent pinned verifier required')
    integer(now_ns, 'verification time')
    policy = bounded_json(verified_bytes(_local_path(policy_path), policy_sha256, 32*1024))
    _exact(policy, ('version','purpose','expected',*ROLE_FIELDS,'valid_from_ns','valid_until_ns'))
    if type(policy['version']) is not int or policy['version'] != 1 or policy['purpose'] != 'G0_BINDING_VERIFICATION_POLICY':
        raise ValueError('G0 external policy schema')
    _exact(policy['expected'], BINDING_FIELDS)
    for name, pin in policy['expected'].items():
        digest(pin, 40 if name in ('source_sha','tree_sha') else 64)
    for name in ROLE_FIELDS:
        if type(policy[name]) is not str or not 1 <= len(policy[name]) <= 128:
            raise ValueError('G0 authority identity')
    if policy['owner_id'] == policy['provider_id']:
        raise ValueError('G0 separate owner/provider authorities required')
    start = integer(policy['valid_from_ns'], 'policy start')
    end = integer(policy['valid_until_ns'], 'policy end')
    if not start <= now_ns <= end or end-start > 86400*1_000_000_000:
        raise ValueError('G0 policy validity window')
    data = verified_bytes(_local_path(manifest_path), manifest_sha256, 64*1024)
    m = bounded_json(data)
    _exact(m, ('version','purpose','binding',*ROLE_FIELDS,'issued_at_ns','expires_at_ns','nonce','signatures'))
    if type(m['version']) is not int or m['version'] != 1 or m['purpose'] != 'G0_READ_ONLY_BINDING_RECEIPT':
        raise ValueError('G0 receipt domain/schema')
    _exact(m['binding'], BINDING_FIELDS)
    if m['binding'] != policy['expected'] or any(m[k] != policy[k] for k in ROLE_FIELDS):
        raise ValueError('G0 independently pinned binding mismatch')
    issued = integer(m['issued_at_ns'], 'receipt issued')
    expires = integer(m['expires_at_ns'], 'receipt expires')
    if not start <= issued <= now_ns <= expires <= end or issued >= expires:
        raise ValueError('G0 receipt time window')
    digest(m['nonce'])
    _exact(m['signatures'], ('owner','provider'))
    trust = load_trust_store(_local_path(trust_store_path), trust_store_sha256)
    public_keys = []
    for role in ('owner','provider'):
        public = trust.key(policy[role+'_id'], policy[role+'_key_id'], issued)
        if trust.key(policy[role+'_id'], policy[role+'_key_id'], now_ns) != public:
            raise ValueError('G0 key validity changed')
        if public in PUBLIC_SOFTWARE_FIXTURE_KEYS or public in public_keys:
            raise ValueError('G0 public fixture/shared authority key rejected')
        public_keys.append(public)
    unsigned = {k:v for k,v in m.items() if k != 'signatures'}
    message = DOMAIN + canonical_bytes(unsigned)
    for role, public in zip(('owner','provider'), public_keys):
        if verifier.verify(public, message, decode64(m['signatures'][role],64)) is not True:
            raise ValueError('G0 signature verifier did not attest success')
    return {'status':'BLOCKED', 'signatures_verified':True,
        'target_truth':'NOT_ESTABLISHED_BY_SIGNATURE',
        'manifest_sha256':sha256(data).hexdigest(), 'policy_sha256':policy_sha256,
        'trust_store_sha256':trust_store_sha256, 'verification_time_ns':now_ns,
        'replay_protection':'NOT_IMPLEMENTED_NO_ADMISSION',
        'blockers':['INDEPENDENT_FACT_AND_RECEIPT_REVIEW_REQUIRED',
                    'DURABLE_REPLAY_REGISTRY_REQUIRED','G0_ADMISSION_NOT_IMPLEMENTED'],
        'physical_g0':'PLAN_READY_TARGET_EVIDENCE_BLOCKED',
        'physical_g1':'NOT_AUTHORIZED', 'g1_execute':'NOT_AUTHORIZED',
        'g1_cleanup':'NOT_AUTHORIZED', 'deployment':'NO-GO', 'trading':'NO-GO'}
