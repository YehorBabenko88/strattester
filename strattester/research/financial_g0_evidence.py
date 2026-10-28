"""Bounded read-only inspection of G0 claims. This is not an attestation verifier.

No claimed observation, digest or receipt can authorize target execution here.
Only the externally pinned manifest is read; referenced artifacts are not opened.
"""
import re

from .financial_executable_inventory import _local_path
from .financial_snapshot import bounded_json, verified_bytes

GROUP_FIELDS = {
    'host_identity': (),
    'os_and_powershell': (),
    'python_base_and_venv': ('executable_roster_sha256',),
    'torch_and_dependencies': ('wheel_lock_sha256', 'installed_metadata_sha256'),
    'cpu_ram_disk_and_limits': ('enforcement_receipt_sha256',),
    'gpu_driver_and_cuda': ('real_gpu_execution_evidence_sha256',),
    'processes_and_services': ('pid_creation_identity_bindings_sha256',),
    'tcp_and_udp_ports': ('pid_to_process_bindings_sha256',),
    'acl_namespace_and_mounts': ('ancestor_acl_roster_sha256', 'backing_volume_identity_sha256'),
    'source_and_database_ownership': ('grid_postgresql_metaanalyse_ownership_roster_sha256', 'producer_receipts_sha256'),
}
STATES = frozenset(('OBSERVED', 'EMPTY', 'MISSING', 'UNAVAILABLE', 'NOT_COLLECTED'))
G0_BLOCKED = 'PLAN_READY_TARGET_EVIDENCE_BLOCKED'


def _exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('G0 schema fields rejected')


def _pin(value, length=64):
    if value is not None and (type(value) is not str or re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is None):
        raise ValueError('G0 digest rejected')


def inspect_g0_evidence(manifest_path, manifest_sha256):
    p = bounded_json(verified_bytes(_local_path(manifest_path), manifest_sha256, 128 * 1024))
    _exact(p, ('version', 'purpose', 'manifest_state', 'execution_authorized', 'release_binding',
        'collector_contract', 'target', 'facts', 'command_captures', 'observation_states',
        'required_private_bindings', 'stop_conditions', 'physical_g0_readiness', 'physical_g1', 'trading'))
    if (type(p['version']) is not int or p['version'] != 1
        or p['purpose'] != 'TARGET_SPECIFIC_G0_EVIDENCE_MANIFEST'
        or p['manifest_state'] != 'PLAN_ONLY_NOT_COLLECTED'
        or p['execution_authorized'] is not False
        or p['physical_g0_readiness'] != G0_BLOCKED
        or p['physical_g1'] != 'NOT_AUTHORIZED' or p['trading'] != 'NO-GO'):
        raise ValueError('G0 non-authorizing envelope required')
    release = p['release_binding']
    _exact(release, ('source_sha', 'tree_sha', 'package_sha256', 'command_manifest_sha256'))
    for key, value in release.items(): _pin(value, 40 if key in ('source_sha', 'tree_sha') else 64)
    c = p['collector_contract']
    _exact(c, ('schema', 'observation_contract_version', 'artifact_sha256', 'capture_sha256', 'capture_state'))
    if (type(c['schema']) is not int or c['schema'] != 1
        or type(c['observation_contract_version']) is not int or c['observation_contract_version'] != 2
        or type(c['capture_state']) is not str or c['capture_state'] not in STATES):
        raise ValueError('G0 collector contract rejected')
    _pin(c['artifact_sha256']); _pin(c['capture_sha256'])
    if c['capture_state'] == 'NOT_COLLECTED' and c['capture_sha256'] is not None:
        raise ValueError('G0 uncollected capture cannot have receipt')
    target = p['target']
    _exact(target, ('label', 'expected_host_identity_sha256', 'observed_host_identity_sha256',
        'independent_identity_receipt_sha256', 'binding_status', 'protected_nodes'))
    label = target['label']
    if label is not None and (type(label) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', label)
        or label.split('.')[0].upper() in ('LS5', 'PC4')):
        raise ValueError('G0 target identity rejected')
    if target['binding_status'] != 'UNRESOLVED' or target['protected_nodes'] != ['LS5', 'PC4']:
        raise ValueError('G0 target remains unresolved')
    for key in ('expected_host_identity_sha256', 'observed_host_identity_sha256', 'independent_identity_receipt_sha256'):
        _pin(target[key])
    _exact(p['facts'], GROUP_FIELDS)
    groups = {}
    for name, extra in GROUP_FIELDS.items():
        fact = p['facts'][name]
        hashes = ('owner_receipt_sha256', *extra)
        _exact(fact, ('capture_state', 'observed', *hashes))
        state, observed = fact['capture_state'], fact['observed']
        if type(state) is not str or state not in STATES:
            raise ValueError('G0 observation state rejected')
        if ((state in ('NOT_COLLECTED', 'UNAVAILABLE') and observed is not None)
            or (state == 'EMPTY' and observed != [])
            or (state in ('OBSERVED', 'MISSING') and (type(observed) not in (dict, list) or not observed))):
            raise ValueError('G0 observation state/value mismatch')
        for key in hashes:
            _pin(fact[key])
            if state == 'NOT_COLLECTED' and fact[key] is not None:
                raise ValueError('G0 uncollected fact cannot have receipt')
        groups[name] = {'claimed_state': state, 'admission': 'BLOCKED',
            'reason': 'INDEPENDENT_TARGET_ATTESTATION_REQUIRED'}
    # Descriptions and command captures are untrusted bounded JSON, never policy,
    # instructions, executable paths, or facts admitted by this function.
    return {'status': 'BLOCKED', 'inspection': 'SCHEMA_ONLY_UNVERIFIED_SELF_REPORT',
        'manifest_sha256': manifest_sha256, 'groups': groups,
        'physical_g0_readiness': G0_BLOCKED, 'physical_g1': 'NOT_AUTHORIZED', 'trading': 'NO-GO'}
