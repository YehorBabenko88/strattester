"""Pure, nonauthorizing G0 prerequisite review; never opens declared paths.

Inputs are private, already parsed review-plan mappings. Results expose field
names only. Hash-shaped claims and complete plans never establish physical truth.
"""
import re
from pathlib import PureWindowsPath

_SELECTION = ('vm_selection', 'hypervisor_provider_id', 'vm_identity_uuid', 'vm_owner',
              'authorized_sandbox_paths', 'authorized_evidence_paths',
              'private_identity_receipt_delivery', 'snapshot_rollback_guarantees')
_BOUNDARY = ('tool_absolute_path', 'tool_sha256', 'independent_enforcement_receipt_sha256',
             'wall_seconds_per_command', 'stdout_stderr_bytes_per_command_combined',
             'minimum_free_disk_bytes', 'operator_abort_identity')
_STORAGE = ('root', 'backing_volume_identity_sha256', 'owner_sid', 'reviewer_sid',
            'ancestor_acl_receipt_sha256', 'encryption_and_key_custody_receipt_sha256',
            'retention_policy_receipt_sha256', 'quota_receipt_sha256')
_MISSING = frozenset(('NOT_SELECTED', 'NOT_COLLECTED', 'NOT_AUTHORIZED', 'NOT_DEFINED',
                      'NOT_VERIFIED'))


def inspect_g0_preflight(selection, capture):
    """Return missing/invalid/unverified declarations; always BLOCKED.

    This API does no IO, cryptography, target selection, inventory, execution or
    receipt dereferencing. Presence and syntax are review aids, never admission.
    """
    if (type(selection) is not dict or type(capture) is not dict
        or type(selection.get('version')) is not int or selection['version'] != 1
        or type(capture.get('version')) is not int or capture['version'] != 1
        or selection.get('evidence_kind') != 'OWNER_DECLARATION_NOT_TARGET_ATTESTATION'
        or capture.get('purpose') != 'PRIVATE_READ_ONLY_G0_CAPTURE_REVIEW_PLAN'
        or selection.get('g0_qualification') != 'BLOCKED'
        or selection.get('g1_execute') != 'NOT_AUTHORIZED'
        or selection.get('g1_cleanup') != 'NOT_AUTHORIZED'
        or selection.get('deployment') != 'NO-GO'
        or selection.get('physical_collection_executed') is not False
        or selection.get('protected_nodes') != ['LS5', 'PC4']
        or capture.get('execution_authorized') is not False
        or capture.get('physical_g1') != 'NOT_AUTHORIZED'
        or capture.get('physical_g0') != 'PLAN_READY_TARGET_EVIDENCE_BLOCKED'
        or type(capture.get('cleanup_review')) is not dict
        or capture['cleanup_review'].get('cleanup_authorized') is not False):
        raise ValueError('G0 nonauthorizing envelope required')
    missing, invalid, unverified = [], [], []
    groups = [('selection', selection, _SELECTION),
              ('capture', capture, ('target_identity_receipt_sha256', 'command_manifest_sha256'))]
    for section, fields in (('capture_boundary', _BOUNDARY), ('private_storage', _STORAGE)):
        value = capture.get(section)
        if type(value) is not dict:
            raise ValueError('G0 review section required')
        groups.append(('capture.' + section, value, fields))
    limits = {'wall_seconds_per_command': (1, 30),
              'stdout_stderr_bytes_per_command_combined': (1, 8388608),
              'minimum_free_disk_bytes': (2147483648, 2**63 - 1)}
    for prefix, values, fields in groups:
        for field in fields:
            value = values.get(field)
            name = prefix + '.' + field
            if value is None or (type(value) is str and (not value.strip() or value in _MISSING)):
                missing.append(name)
                continue
            valid = type(value) is str and 0 < len(value) <= 4096
            if field in limits:
                low, high = limits[field]
                valid = type(value) is int and low <= value <= high
            elif field.endswith('_sha256'):
                valid = type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None
            elif field in ('tool_absolute_path', 'root'):
                valid = (valid and PureWindowsPath(value).is_absolute()
                         and re.match(r'^[A-Za-z]:\\', value) is not None
                         and '..' not in PureWindowsPath(value).parts
                         and '<' not in value and '>' not in value)
            if not valid:
                invalid.append(name)
            else:
                unverified.append(name)
    return {'version': 1, 'purpose': 'G0_NONAUTHORIZING_PREFLIGHT',
            'missing_fields': sorted(missing), 'invalid_fields': sorted(invalid),
            'unverified_claims': sorted(unverified),
            'independent_verification': 'NOT_PERFORMED',
            'g0_qualification': 'BLOCKED', 'execution_authorized': False,
            'g1_execute': 'NOT_AUTHORIZED', 'g1_cleanup': 'NOT_AUTHORIZED',
            'deployment': 'NO-GO', 'trading': 'NO-GO'}
