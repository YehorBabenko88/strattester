"""Independent adversarial software-only qualification review; no physical IO."""
import base64
import copy
import json
from pathlib import Path
import runpy

import pytest


def synthetic(root):
    result = runpy.run_path(str(Path(__file__).with_name('test_g0_qualification_v2.py')))['fixture'](root)
    q, e = result[:2]
    q['private_evidence']['backing_volume_identity_sha256'] = e['facts']['acl_namespace_and_mounts']['backing_volume_identity_sha256']
    result[7]()
    return result


def blocked(result):
    assert result['status'] == 'BLOCKED'
    assert result['contract_verified'] is True
    assert result['physical_g1'] == result['g1_execute'] == result['g1_cleanup'] == 'NOT_AUTHORIZED'
    assert result['trading'] == result['deployment'] == 'NO-GO'
    assert result['replay_protection'] == 'NOT_IMPLEMENTED_NO_ADMISSION'


@pytest.mark.parametrize('field,value', [
    ('start_time_ns', True), ('end_time_ns', 130.0), ('exit_code', False),
    ('timed_out', 0), ('output_truncated', 0), ('stdout_bytes', 10.0),
    ('stderr_bytes', False), ('capture_bytes', '10'), ('minimum_free_disk_bytes', True),
    ('command_id', ['G0-01']), ('observation_state', ['OBSERVED']),
])
def test_independent_capture_type_confusion(tmp_path, field, value):
    q, e, _, _, _, _, _, publish, verify, _ = synthetic(tmp_path)
    q['captures'][0][field] = value
    e['command_captures'] = copy.deepcopy(q['captures'])
    publish()
    with pytest.raises(ValueError):
        verify()


@pytest.mark.parametrize('attack', ['provider_identity', 'evidence_root', 'tree', 'tool',
                                  'role_scope', 'fixture_key', 'stale', 'namespace', 'reused_other_vm'])
def test_independent_binding_trust_and_replay_attacks(tmp_path, attack):
    q, e, review, replay, m, policy, trust, publish, verify, _ = synthetic(tmp_path)
    if attack in ('provider_identity', 'evidence_root'):
        q['identity'][attack + '_sha256'] = '0'*64
    elif attack == 'tree':
        q['release']['tree_sha'] = '0'*40
    elif attack == 'tool':
        q['captures'][0]['tool_sha256'] = '0'*64
        e['command_captures'] = copy.deepcopy(q['captures'])
    elif attack == 'role_scope':
        trust['keys'][0]['producer_id'] = 'provider'
    elif attack == 'fixture_key':
        trust['keys'][0]['public_key_b64'] = base64.b64encode(bytes.fromhex(
            '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')).decode()
    elif attack == 'stale':
        replay['observed_at_ns'] = 119
    elif attack == 'namespace':
        replay['namespace_sha256'] = '0'*64
    else:
        replay['entries'] = [dict(nonce_sha256=m['nonce'], vm_identity_sha256='0'*64, receipt_sha256='0'*64)]
    publish()
    with pytest.raises(ValueError):
        verify()


def test_independent_private_volume_must_match_observed_mount_volume(tmp_path):
    q, e, _, _, _, _, _, publish, verify, _ = synthetic(tmp_path)
    # Align the valid baseline, then substitute only one duplicate volume identity.
    q['private_evidence']['backing_volume_identity_sha256'] = e['facts']['acl_namespace_and_mounts']['backing_volume_identity_sha256']
    publish()
    blocked(verify())
    q['private_evidence']['backing_volume_identity_sha256'] = '0'*64
    publish()
    with pytest.raises(ValueError):
        verify()


@pytest.mark.parametrize('group,field', [
    ('python_base_and_venv', 'executable_roster_sha256'),
    ('torch_and_dependencies', 'wheel_lock_sha256'),
    ('torch_and_dependencies', 'installed_metadata_sha256'),
    ('cpu_ram_disk_and_limits', 'enforcement_receipt_sha256'),
    ('gpu_driver_and_cuda', 'real_gpu_execution_evidence_sha256'),
    ('processes_and_services', 'pid_creation_identity_bindings_sha256'),
    ('tcp_and_udp_ports', 'pid_to_process_bindings_sha256'),
    ('acl_namespace_and_mounts', 'ancestor_acl_roster_sha256'),
    ('acl_namespace_and_mounts', 'backing_volume_identity_sha256'),
    ('source_and_database_ownership', 'grid_postgresql_metaanalyse_ownership_roster_sha256'),
    ('source_and_database_ownership', 'producer_receipts_sha256'),
])
def test_independent_observed_private_bindings_cannot_be_null(tmp_path, group, field):
    _, e, _, _, _, _, _, publish, verify, _ = synthetic(tmp_path)
    e['facts'][group][field] = None
    publish()
    with pytest.raises(ValueError):
        verify()


def test_independent_no_referenced_io_or_public_raw_fields(tmp_path, monkeypatch):
    import socket
    import sqlite3
    import subprocess
    from strattester.research import financial_g0_qualification as qualification
    from strattester.research import financial_g0_receipt as receipt
    from strattester.research import financial_g0_evidence as evidence
    from strattester.research import financial_signatures as signatures
    _, e, _, _, _, _, _, publish, verify, args = synthetic(tmp_path)
    canary = 'PRIVATE_CANARY_https://invalid.invalid/secret'
    e['facts']['host_identity']['observed']['diagnostic_path'] = canary
    e['facts']['host_identity']['observed']['raw_stdout'] = canary
    publish()
    allowed = {Path(value).resolve() for key, value in args().items() if key.endswith('_path')}
    reads = []
    def bounded_reader(real):
        def read(path, *pos, **kw):
            assert Path(path).resolve() in allowed
            reads.append(Path(path).name)
            return real(path, *pos, **kw)
        return read
    for module in (qualification, receipt, evidence, signatures):
        monkeypatch.setattr(module, 'verified_bytes', bounded_reader(module.verified_bytes))
    def forbidden(*args, **kwargs):
        raise AssertionError('external or referenced IO is forbidden')
    # Cryptography is independently covered above; isolate the inspection IO boundary here.
    monkeypatch.setattr(signatures.OpenSSLVerifier, 'verify', lambda self, *args: True)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    result = verify()
    blocked(result)
    assert canary not in json.dumps(result)
    assert set(reads) == {'review.json', 'qualification.json', 'evidence.json', 'receipt.json', 'policy.json', 'trust.json', 'replay.json'}

