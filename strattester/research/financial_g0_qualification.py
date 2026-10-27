"""Bounded G0 v2 claim consistency review. No collection, replay write or admission.

Only the seven explicitly supplied, externally pinned documents are read. A replay
snapshot can disprove freshness but cannot prove atomic, durable nonce consumption.
Capture limits and private controls are claims; no OS enforcement is implemented.
"""
from hashlib import sha256
from functools import wraps

from .financial_contract import digest, integer
from .financial_executable_inventory import _local_path
from .financial_g0_evidence import GROUP_FIELDS, _exact, inspect_g0_evidence
from .financial_g0_receipt import verify_g0_receipt
from .financial_snapshot import bounded_json, canonical_bytes, verified_bytes

_CAPTURE_FIELDS = (
    'command_id', 'exact_argv_manifest_sha256', 'tool_sha256',
    'target_identity_receipt_sha256', 'start_time_ns', 'end_time_ns', 'exit_code',
    'timed_out', 'output_truncated', 'stdout_sha256', 'stderr_sha256',
    'stdout_bytes', 'stderr_bytes', 'capture_bytes', 'minimum_free_disk_bytes',
    'observation_state', 'private_owner_receipt_sha256',
)
_IDENTITY_FIELDS = (
    'owner_id', 'provider_id', 'vm_identity_sha256', 'provider_identity_sha256',
    'guest_identity_sha256', 'identity_receipt_sha256', 'snapshot_generation_sha256',
    'sandbox_root_sha256', 'evidence_root_sha256',
)
_PRIVATE_FIELDS = (
    'delivery_receipt_sha256', 'acl_scope_receipt_sha256', 'evidence_root_sha256',
    'backing_volume_identity_sha256', 'encryption_and_key_custody_receipt_sha256',
    'retention_policy_receipt_sha256', 'quota_receipt_sha256',
    'owner_identity_sha256', 'reviewer_identity_sha256',
)
_DOCUMENTS = ('qualification', 'evidence', 'manifest', 'policy', 'trust_store', 'replay')
_EMPTY_DIGEST = sha256(b'').hexdigest()


def _read(path, pin, budget):
    return bounded_json(verified_bytes(_local_path(path), pin, budget))


def _require(condition):
    if not condition:
        raise ValueError('G0 qualification contract rejected')


def _list(value, maximum, minimum=0):
    _require(type(value) is list and minimum <= len(value) <= maximum)
    return value


def _text(value):
    _require(type(value) is str and 1 <= len(value) <= 128 and value.strip() == value
             and all(ord(c) >= 32 and ord(c) != 127 for c in value))
    return value


def _number(value, low=0, high=2**63-1):
    integer(value, 'G0 bounded integer', low)
    _require(value <= high)
    return value


def _private_errors(function):
    @wraps(function)
    def inspect(**kwargs):
        try:
            return function(**kwargs)
        except (OSError, ValueError, TypeError, KeyError):
            # Library callers must not expose private filenames or JSON values,
            # including through an implicit chained exception traceback.
            raise ValueError('G0 qualification review rejected') from None
    return inspect


def _replay(snapshot, policy, receipt, receipt_sha256, now_ns):
    _exact(snapshot, ('version', 'purpose', 'namespace_sha256', 'sequence', 'observed_at_ns', 'entries'))
    _require(type(snapshot['version']) is int and snapshot['version'] == 1
             and snapshot['purpose'] == 'G0_REPLAY_REVIEW_SNAPSHOT')
    digest(snapshot['namespace_sha256'])
    _number(snapshot['sequence'])
    at = _number(snapshot['observed_at_ns'])
    _require(snapshot['namespace_sha256'] == policy['replay_namespace_sha256']
             and snapshot['sequence'] == policy['replay_sequence']
             and policy['valid_from_ns'] <= at <= now_ns
             and now_ns-at <= policy['maximum_replay_age_ns'])
    seen = set()
    for entry in _list(snapshot['entries'], 512):
        _exact(entry, ('nonce_sha256', 'vm_identity_sha256', 'receipt_sha256'))
        for value in entry.values():
            digest(value)
        nonce = entry['nonce_sha256']
        # Global within the externally selected namespace; changing VM cannot reuse it.
        _require(nonce not in seen and nonce != receipt['nonce']
                 and entry['receipt_sha256'] != receipt_sha256)
        seen.add(nonce)


def _captures(qualification, evidence, policy, receipt, now_ns):
    bounds = qualification['capture_constraints']
    _exact(bounds, ('wall_seconds_per_command', 'stdout_stderr_bytes_per_command_combined',
                    'minimum_free_disk_bytes', 'independent_enforcement_receipt_sha256'))
    wall = _number(bounds['wall_seconds_per_command'], 1, 30)
    cap = _number(bounds['stdout_stderr_bytes_per_command_combined'], 1, 8388608)
    floor = _number(bounds['minimum_free_disk_bytes'], 2147483648)
    digest(bounds['independent_enforcement_receipt_sha256'])
    _require(bounds['independent_enforcement_receipt_sha256'] == receipt['binding']['capture_controls_receipt_sha256'])
    requirements = {}
    groups = set()
    for requirement in _list(policy['command_requirements'], 64, 1):
        _exact(requirement, ('command_id', 'observation_group', 'exact_argv_manifest_sha256',
                             'tool_sha256', 'required_fields', 'empty_allowed'))
        command = _text(requirement['command_id'])
        group = _text(requirement['observation_group'])
        _require(command not in requirements and group not in groups and group in GROUP_FIELDS)
        groups.add(group)
        for field in ('exact_argv_manifest_sha256', 'tool_sha256'):
            digest(requirement[field])
        _require(type(requirement['empty_allowed']) is bool)
        fields = _list(requirement['required_fields'], 64, 1)
        for field in fields:
            _text(field)
        _require(len(set(fields)) == len(fields))
        requirements[command] = requirement
    _require(groups == set(GROUP_FIELDS))
    seen = set()
    captures = _list(qualification['captures'], 64, 1)
    # Python equality conflates False/0 and True/1, including nested mappings.
    _require(canonical_bytes(captures) == canonical_bytes(evidence['command_captures']))
    for capture in captures:
        _exact(capture, _CAPTURE_FIELDS)
        command = _text(capture['command_id'])
        _require(command in requirements and command not in seen)
        seen.add(command)
        requirement = requirements[command]
        fact = evidence['facts'][requirement['observation_group']]
        # Template/schema inspection intentionally permits absent claims. A
        # collected qualification contract requires every auxiliary binding.
        for field in ('owner_receipt_sha256', *GROUP_FIELDS[requirement['observation_group']]):
            digest(fact[field])
        for field in _CAPTURE_FIELDS:
            if field.endswith('_sha256'):
                digest(capture[field])
        _require(capture['tool_sha256'] == requirement['tool_sha256']
                 and capture['exact_argv_manifest_sha256'] == requirement['exact_argv_manifest_sha256']
                 and capture['target_identity_receipt_sha256'] == qualification['identity']['identity_receipt_sha256']
                 and capture['private_owner_receipt_sha256'] == fact['owner_receipt_sha256'])
        start = _number(capture['start_time_ns'])
        end = _number(capture['end_time_ns'])
        _require(receipt['issued_at_ns'] <= start <= end <= min(now_ns, receipt['expires_at_ns'])
                 and end-start <= wall*1_000_000_000)
        _require(type(capture['timed_out']) is bool and capture['timed_out'] is False
                 and type(capture['output_truncated']) is bool and capture['output_truncated'] is False)
        _require(_number(capture['exit_code']) == 0)
        stdout = _number(capture['stdout_bytes'], 0, cap)
        stderr = _number(capture['stderr_bytes'], 0, cap)
        _require(_number(capture['capture_bytes'], 0, cap) == stdout+stderr)
        _require(_number(capture['minimum_free_disk_bytes'], floor) >= floor)
        for stream, size in (('stdout', stdout), ('stderr', stderr)):
            _require((capture[stream+'_sha256'] == _EMPTY_DIGEST) == (size == 0))
        state = capture['observation_state']
        _require(type(state) is str and state in ('OBSERVED', 'EMPTY') and state == fact['capture_state'])
        if state == 'EMPTY':
            _require(requirement['empty_allowed'] is True and fact['observed'] == [])
        else:
            rows = fact['observed'] if type(fact['observed']) is list else [fact['observed']]
            _require(bool(rows))
            for row in rows:
                _require(type(row) is dict)
                for field in requirement['required_fields']:
                    _require(field in row and row[field] is not None
                             and (type(row[field]) is not str or bool(row[field].strip())))
    _require(seen == set(requirements))


@_private_errors
def verify_g0_qualification(*, qualification_path, qualification_sha256,
                            evidence_path, evidence_sha256, manifest_path, manifest_sha256,
                            policy_path, policy_sha256, trust_store_path, trust_store_sha256,
                            review_policy_path, review_policy_sha256, replay_path, replay_sha256,
                            verifier, now_ns):
    """Verify pinned claim consistency and signatures; return BLOCKED, never PASS.

    Callers independently supply all pins, verifier and trusted time. Replay input
    is a review snapshot only; concurrent checks can both see an unused nonce.
    """
    _number(now_ns)
    review = _read(review_policy_path, review_policy_sha256, 32*1024)
    _exact(review, ('version', 'purpose', 'expected', 'challenge_nonce_sha256',
                    'replay_namespace_sha256', 'replay_sequence', 'maximum_replay_age_ns',
                    'valid_from_ns', 'valid_until_ns', 'command_requirements'))
    _require(type(review['version']) is int and review['version'] == 2
             and review['purpose'] == 'G0_EXTERNAL_QUALIFICATION_REVIEW_POLICY')
    _exact(review['expected'], (name+'_sha256' for name in _DOCUMENTS))
    pins = dict(qualification=qualification_sha256, evidence=evidence_sha256,
                manifest=manifest_sha256, policy=policy_sha256,
                trust_store=trust_store_sha256, replay=replay_sha256)
    for name, value in pins.items():
        digest(value)
        _require(review['expected'][name+'_sha256'] == value)
    for field in ('challenge_nonce_sha256', 'replay_namespace_sha256'):
        digest(review[field])
    _number(review['replay_sequence'])
    _number(review['maximum_replay_age_ns'], 1, 30*1_000_000_000)
    start = _number(review['valid_from_ns'])
    end = _number(review['valid_until_ns'])
    _require(start <= now_ns <= end and 0 < end-start <= 86400*1_000_000_000)
    signed = verify_g0_receipt(manifest_path=manifest_path, manifest_sha256=manifest_sha256,
        policy_path=policy_path, policy_sha256=policy_sha256, trust_store_path=trust_store_path,
        trust_store_sha256=trust_store_sha256, verifier=verifier, now_ns=now_ns)
    # A second read is still checked against the same external pin; no unpinned references.
    receipt = _read(manifest_path, manifest_sha256, 64*1024)
    _require(receipt['nonce'] == review['challenge_nonce_sha256'])
    _replay(_read(replay_path, replay_sha256, 128*1024), review, receipt, manifest_sha256, now_ns)
    qualification = _read(qualification_path, qualification_sha256, 128*1024)
    _exact(qualification, ('version', 'purpose', 'evidence_kind', 'execution_authorized',
        'physical_g1', 'trading', 'release', 'identity', 'capture_constraints', 'private_evidence', 'captures'))
    _require(type(qualification['version']) is int and qualification['version'] == 2
        and qualification['purpose'] == 'G0_QUALIFICATION_CLAIMS'
        and qualification['evidence_kind'] in ('SYNTHETIC_SOFTWARE_ONLY', 'UNVERIFIED_PRIVATE_TARGET_CLAIMS')
        and qualification['execution_authorized'] is False
        and qualification['physical_g1'] == 'NOT_AUTHORIZED' and qualification['trading'] == 'NO-GO')
    inspect_g0_evidence(evidence_path, evidence_sha256)
    evidence = _read(evidence_path, evidence_sha256, 128*1024)
    _exact(evidence['observation_states'], ('OBSERVED', 'EMPTY', 'MISSING', 'UNAVAILABLE', 'NOT_COLLECTED'))
    for description in evidence['observation_states'].values():
        _require(type(description) is str and 1 <= len(description) <= 512)
    for field in ('required_private_bindings', 'stop_conditions'):
        for description in _list(evidence[field], 64, 1):
            _require(type(description) is str and 1 <= len(description) <= 512)
    binding = receipt['binding']
    _require(binding['evidence_manifest_sha256'] == evidence_sha256)
    _exact(qualification['release'], ('source_sha', 'tree_sha', 'package_sha256', 'command_manifest_sha256'))
    for field, value in qualification['release'].items():
        digest(value, 40 if field in ('source_sha', 'tree_sha') else 64)
        _require(value == binding[field] == evidence['release_binding'][field])
    identity = qualification['identity']
    _exact(identity, _IDENTITY_FIELDS)
    for field, value in identity.items():
        if field in ('owner_id', 'provider_id'):
            _text(value)
            _require(value == receipt[field])
        else:
            digest(value)
            if field in binding:
                _require(value == binding[field])
    target = evidence['target']
    _require(identity['identity_receipt_sha256'] == target['independent_identity_receipt_sha256']
             and identity['guest_identity_sha256'] == target['expected_host_identity_sha256']
             == target['observed_host_identity_sha256'])
    collector = evidence['collector_contract']
    _require(collector['capture_state'] == 'OBSERVED')
    digest(collector['artifact_sha256']); digest(collector['capture_sha256'])
    private = qualification['private_evidence']
    _exact(private, _PRIVATE_FIELDS)
    for value in private.values():
        digest(value)
    _require(private['delivery_receipt_sha256'] == binding['private_delivery_receipt_sha256']
        and private['acl_scope_receipt_sha256'] == binding['acl_scope_receipt_sha256']
        and private['evidence_root_sha256'] == binding['evidence_root_sha256']
        and private['backing_volume_identity_sha256'] == evidence['facts']['acl_namespace_and_mounts']['backing_volume_identity_sha256']
        and private['owner_identity_sha256'] != private['reviewer_identity_sha256'])
    _captures(qualification, evidence, review, receipt, now_ns)
    return dict(status='BLOCKED', contract_verified=True, signatures_verified=signed['signatures_verified'],
        evidence_kind=qualification['evidence_kind'], target_truth='NOT_ESTABLISHED_BY_SIGNATURE',
        qualification_sha256=qualification_sha256, evidence_sha256=evidence_sha256,
        review_policy_sha256=review_policy_sha256, replay_snapshot_sha256=replay_sha256,
        replay_protection='NOT_IMPLEMENTED_NO_ADMISSION', capture_enforcement='NOT_ESTABLISHED_BY_CLAIMS',
        blockers=['INDEPENDENT_PHYSICAL_EVIDENCE_REQUIRED', 'DURABLE_REPLAY_REGISTRY_REQUIRED',
                  'INDEPENDENT_CAPTURE_ENFORCEMENT_REQUIRED', 'G0_ADMISSION_NOT_IMPLEMENTED'],
        physical_g0='PLAN_READY_TARGET_EVIDENCE_BLOCKED', physical_g1='NOT_AUTHORIZED',
        g1_execute='NOT_AUTHORIZED', g1_cleanup='NOT_AUTHORIZED', deployment='NO-GO', trading='NO-GO')
