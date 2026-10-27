"""Software fixtures only; no target operations or admission."""
import copy
import json
from pathlib import Path
import pytest
from strattester.research import financial_g0_preflight as preflight

ROOT = Path(__file__).resolve().parents[2]

def plans():
    return tuple(json.loads((ROOT / 'docs/readiness' / name).read_text()) for name in (
        'TARGET_G0_SELECTION_STATUS.json', 'TARGET_G0_PRIVATE_CAPTURE_PLAN.template.json'))

def test_templates_report_all_missing_facts_without_echoing_private_values():
    selection, capture = plans()
    result = preflight.inspect_g0_preflight(selection, capture)
    assert result['g0_qualification'] == 'BLOCKED'
    assert result['execution_authorized'] is False
    for field in ('vm_selection', 'hypervisor_provider_id', 'vm_identity_uuid', 'vm_owner',
                  'authorized_sandbox_paths', 'authorized_evidence_paths',
                  'private_identity_receipt_delivery', 'snapshot_rollback_guarantees'):
        assert 'selection.' + field in result['missing_fields']
    assert 'capture.private_storage.owner_sid' in result['missing_fields']
    assert result['g1_execute'] == result['g1_cleanup'] == 'NOT_AUTHORIZED'
    assert result['deployment'] == result['trading'] == 'NO-GO'

@pytest.mark.parametrize('field,value', [
    ('wall_seconds_per_command', True), ('wall_seconds_per_command', 31),
    ('wall_seconds_per_command', 0), ('wall_seconds_per_command', float('nan')),
    ('stdout_stderr_bytes_per_command_combined', 8388609),
    ('minimum_free_disk_bytes', 2147483647),
    ('tool_absolute_path', r'\\server\private\capture.exe'),
    ('tool_absolute_path', 'relative.exe'), ('tool_sha256', 'g' * 64),
])
def test_invalid_boundary_claims_are_reported(field, value):
    selection, capture = plans()
    capture['capture_boundary'][field] = value
    result = preflight.inspect_g0_preflight(selection, capture)
    assert 'capture.capture_boundary.' + field in result['invalid_fields']

@pytest.mark.parametrize('section,field', [
    ('capture_boundary', 'tool_sha256'),
    ('capture_boundary', 'independent_enforcement_receipt_sha256'),
    ('private_storage', 'backing_volume_identity_sha256'),
    ('private_storage', 'ancestor_acl_receipt_sha256'),
    ('private_storage', 'encryption_and_key_custody_receipt_sha256'),
    ('private_storage', 'retention_policy_receipt_sha256'),
    ('private_storage', 'quota_receipt_sha256'),
])
def test_hash_shaped_claims_remain_unverified(section, field):
    selection, capture = plans()
    capture[section][field] = 'a' * 64
    result = preflight.inspect_g0_preflight(selection, capture)
    assert 'capture.' + section + '.' + field in result['unverified_claims']
    assert result['g0_qualification'] == 'BLOCKED'

@pytest.mark.parametrize('mutate', [
    lambda s, c: s.update(g1_execute='AUTHORIZED'),
    lambda s, c: c.update(execution_authorized=True),
    lambda s, c: c['cleanup_review'].update(cleanup_authorized=True),
    lambda s, c: s.update(protected_nodes=[]),
])
def test_authorization_claims_are_rejected(mutate):
    selection, capture = plans()
    mutate(selection, capture)
    with pytest.raises(ValueError, match='nonauthorizing'):
        preflight.inspect_g0_preflight(selection, capture)

def test_no_input_mutation_or_private_values_in_report():
    selection, capture = plans()
    selection['vm_owner'] = 'PRIVATE_OWNER_CANARY'
    capture['private_storage']['root'] = r'C:\PRIVATE_PATH_CANARY'
    before = copy.deepcopy((selection, capture))
    result = preflight.inspect_g0_preflight(selection, capture)
    assert (selection, capture) == before
    assert 'PRIVATE_' not in json.dumps(result)

@pytest.mark.parametrize('section,field', [
    ('selection', field) for field in (
        'vm_selection', 'hypervisor_provider_id', 'vm_identity_uuid', 'vm_owner',
        'authorized_sandbox_paths', 'authorized_evidence_paths',
        'private_identity_receipt_delivery', 'snapshot_rollback_guarantees')
] + [('capture', field) for field in ('target_identity_receipt_sha256', 'command_manifest_sha256')]
  + [('capture.capture_boundary', field) for field in (
      'tool_absolute_path', 'tool_sha256', 'independent_enforcement_receipt_sha256',
      'wall_seconds_per_command', 'stdout_stderr_bytes_per_command_combined',
      'minimum_free_disk_bytes', 'operator_abort_identity')]
  + [('capture.private_storage', field) for field in (
      'root', 'backing_volume_identity_sha256', 'owner_sid', 'reviewer_sid',
      'ancestor_acl_receipt_sha256', 'encryption_and_key_custody_receipt_sha256',
      'retention_policy_receipt_sha256', 'quota_receipt_sha256')])
def test_every_absent_prerequisite_is_reported(section, field):
    selection, capture = plans()
    groups = {'selection': selection, 'capture': capture,
              'capture.capture_boundary': capture['capture_boundary'],
              'capture.private_storage': capture['private_storage']}
    del groups[section][field]
    result = preflight.inspect_g0_preflight(selection, capture)
    assert section + '.' + field in result['missing_fields']
    assert result['g0_qualification'] == 'BLOCKED'
