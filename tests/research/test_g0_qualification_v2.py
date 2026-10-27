"""Literal synthetic qualification v2 fixtures; no target or production constants."""
import copy
from hashlib import sha256
import importlib
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[2]
GROUPS = ('host_identity', 'os_and_powershell', 'python_base_and_venv',
          'torch_and_dependencies', 'cpu_ram_disk_and_limits', 'gpu_driver_and_cuda',
          'processes_and_services', 'tcp_and_udp_ports', 'acl_namespace_and_mounts',
          'source_and_database_ownership')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(value):
    return sha256(encoded(value)).hexdigest()


def fixture(root):
    helper = runpy.run_path(str(Path(__file__).with_name('test_g0_signed_receipt.py')))['fixture']
    m, bp, trust, sign, _ = helper(root)
    evidence = json.loads((ROOT / 'docs/readiness/TARGET_G0_EVIDENCE_MANIFEST.template.json').read_text())
    evidence['collector_contract'].update(capture_state='OBSERVED', capture_sha256='d'*64, artifact_sha256='e'*64)
    evidence['release_binding'] = {k: m['binding'][k] for k in ('source_sha', 'tree_sha', 'package_sha256', 'command_manifest_sha256')}
    evidence['target'].update(label='SYNTHETIC_ONLY', expected_host_identity_sha256='f'*64,
        observed_host_identity_sha256='f'*64, independent_identity_receipt_sha256='1'*64)
    captures, requirements = [], []
    for i, group in enumerate(GROUPS):
        evidence['facts'][group].update(capture_state='OBSERVED', observed={'fixture_value': 1})
        for key in evidence['facts'][group].keys() - {'capture_state', 'observed'}:
            evidence['facts'][group][key] = '2'*64
        requirements.append(dict(command_id=f'G0-{i+1:02}', observation_group=group,
            exact_argv_manifest_sha256='3'*64, tool_sha256='4'*64,
            required_fields=['fixture_value'], empty_allowed=(group == 'tcp_and_udp_ports')))
        captures.append(dict(command_id=f'G0-{i+1:02}', exact_argv_manifest_sha256='3'*64,
            tool_sha256='4'*64, target_identity_receipt_sha256='1'*64,
            start_time_ns=120, end_time_ns=130, exit_code=0, timed_out=False,
            output_truncated=False, stdout_sha256='5'*64, stderr_sha256=sha256(b'').hexdigest(),
            stdout_bytes=10, stderr_bytes=0, capture_bytes=10, minimum_free_disk_bytes=2147483648,
            observation_state='OBSERVED', private_owner_receipt_sha256='2'*64))
    evidence['command_captures'] = copy.deepcopy(captures)
    qualification = dict(version=2, purpose='G0_QUALIFICATION_CLAIMS', evidence_kind='SYNTHETIC_SOFTWARE_ONLY',
        execution_authorized=False, physical_g1='NOT_AUTHORIZED', trading='NO-GO',
        release=copy.deepcopy(evidence['release_binding']),
        identity=dict(owner_id='owner', provider_id='provider', vm_identity_sha256='b'*64,
            provider_identity_sha256='b'*64, guest_identity_sha256='f'*64,
            identity_receipt_sha256='1'*64, snapshot_generation_sha256='b'*64,
            sandbox_root_sha256='b'*64, evidence_root_sha256='b'*64),
        capture_constraints=dict(wall_seconds_per_command=30,
            stdout_stderr_bytes_per_command_combined=8388608, minimum_free_disk_bytes=2147483648,
            independent_enforcement_receipt_sha256='b'*64),
        private_evidence=dict(delivery_receipt_sha256='b'*64, acl_scope_receipt_sha256='b'*64,
            evidence_root_sha256='b'*64, backing_volume_identity_sha256='6'*64,
            encryption_and_key_custody_receipt_sha256='7'*64, retention_policy_receipt_sha256='8'*64,
            quota_receipt_sha256='9'*64, owner_identity_sha256='a'*64, reviewer_identity_sha256='c'*64),
        captures=captures)
    replay = dict(version=1, purpose='G0_REPLAY_REVIEW_SNAPSHOT', namespace_sha256='9'*64,
        sequence=1, observed_at_ns=140, entries=[])
    review = dict(version=2, purpose='G0_EXTERNAL_QUALIFICATION_REVIEW_POLICY',
        expected={}, challenge_nonce_sha256='c'*64, replay_namespace_sha256='9'*64,
        replay_sequence=1, maximum_replay_age_ns=30, valid_from_ns=100, valid_until_ns=200,
        command_requirements=requirements)

    def publish():
        m['binding']['evidence_manifest_sha256'] = pin(evidence)
        bp['expected'] = copy.deepcopy(m['binding'])
        sign()
        for name, value in (('qualification', qualification), ('evidence', evidence), ('replay', replay)):
            (root / (name + '.json')).write_bytes(encoded(value))
        review['expected'] = {name + '_sha256': sha256((root / (file + '.json')).read_bytes()).hexdigest()
            for name, file in [('qualification','qualification'), ('evidence','evidence'),
                              ('manifest','receipt'), ('policy','policy'), ('trust_store','trust'), ('replay','replay')]}
        (root / 'review.json').write_bytes(encoded(review))

    def args():
        result = {name + suffix: value for name, file in [('qualification','qualification'), ('evidence','evidence'),
            ('manifest','receipt'), ('policy','policy'), ('trust_store','trust'), ('replay','replay'), ('review_policy','review')]
            for suffix, value in [('_path', str(root/(file+'.json'))),
                                  ('_sha256', sha256((root/(file+'.json')).read_bytes()).hexdigest())]}
        verifier = runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))['verifier'](root)
        return dict(result, verifier=verifier, now_ns=150)

    def verify(**changes):
        from strattester.research import financial_g0_evidence
        # Missing capability is a deliberate assertion failure, not an import/setup error.
        assert importlib.util.find_spec('strattester.research.financial_g0_qualification'), 'connected qualification verifier missing'
        module = importlib.import_module('strattester.research.financial_g0_qualification')
        return module.verify_g0_qualification(**dict(args(), **changes))

    publish()
    return qualification, evidence, review, replay, m, bp, trust, publish, verify, args


def test_connected_synthetic_claims_are_never_physical_admission(tmp_path):
    *_, verify, args = fixture(tmp_path)
    result = verify()
    assert result['status'] == 'BLOCKED'
    assert result['contract_verified'] is True
    assert result['physical_g1'] == 'NOT_AUTHORIZED' and result['trading'] == 'NO-GO'
    assert result['replay_protection'] == 'NOT_IMPLEMENTED_NO_ADMISSION'
    assert result['target_truth'] == 'NOT_ESTABLISHED_BY_SIGNATURE'
    assert result['physical_g0'] == 'PLAN_READY_TARGET_EVIDENCE_BLOCKED'


@pytest.mark.parametrize('attack', [
    'owner', 'provider', 'guest', 'vm', 'generation', 'root', 'release', 'command_pin',
    'authority_alias', 'shared_key', 'revoked', 'expired', 'challenge', 'replay',
    'stale_replay', 'future_replay', 'replay_sequence', 'replay_namespace', 'replay_duplicate',
    'wall_cap', 'output_cap', 'disk_floor', 'boolean_cap', 'missing_enforcement',
    'duration', 'negative_duration', 'future_capture', 'boolean_time', 'combined_bytes',
    'boolean_bytes', 'over_output', 'disk_exhausted', 'timeout', 'truncated', 'exit',
    'tool', 'argv', 'capture_target', 'owner_receipt', 'capture_state', 'capture_duplicate',
    'capture_missing', 'capture_extra', 'raw_private', 'delivery', 'acl', 'storage_root',
    'missing_encryption', 'same_reviewer', 'empty_required', 'required_property',
    'unknown_qualification', 'boolean_version', 'protected_target', 'missing_group',
])
def test_resigned_and_repinned_semantic_attacks_rejected(tmp_path, attack):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    c = q['captures'][0]
    if attack in ('owner','provider'): q['identity'][attack + '_id'] = 'PRIVATE_CANARY'
    elif attack in ('guest','vm','generation','root'):
        q['identity'][{'guest':'guest_identity_sha256','vm':'vm_identity_sha256',
                      'generation':'snapshot_generation_sha256','root':'sandbox_root_sha256'}[attack]] = '0'*64
    elif attack == 'release': q['release']['source_sha'] = '0'*40
    elif attack == 'command_pin': q['release']['command_manifest_sha256'] = '0'*64
    elif attack == 'authority_alias': m['owner_id'] = bp['owner_id'] = 'provider'
    elif attack == 'shared_key': trust['keys'][1]['public_key_b64'] = trust['keys'][0]['public_key_b64']
    elif attack == 'revoked': trust['keys'][1]['revoked'] = True
    elif attack == 'expired': m['expires_at_ns'] = 149
    elif attack == 'challenge': m['nonce'] = '0'*64
    elif attack == 'replay': replay['entries'] = [dict(nonce_sha256='c'*64, vm_identity_sha256='0'*64, receipt_sha256='0'*64)]
    elif attack == 'stale_replay': replay['observed_at_ns'] = 119
    elif attack == 'future_replay': replay['observed_at_ns'] = 151
    elif attack == 'replay_sequence': replay['sequence'] = 0
    elif attack == 'replay_namespace': replay['namespace_sha256'] = '0'*64
    elif attack == 'replay_duplicate': replay['entries'] = [dict(nonce_sha256='0'*64, vm_identity_sha256='0'*64, receipt_sha256='0'*64)]*2
    elif attack in ('wall_cap','output_cap','disk_floor','boolean_cap','missing_enforcement'):
        key, value = {'wall_cap':('wall_seconds_per_command',31), 'output_cap':('stdout_stderr_bytes_per_command_combined',8388609),
            'disk_floor':('minimum_free_disk_bytes',2147483647), 'boolean_cap':('wall_seconds_per_command',True),
            'missing_enforcement':('independent_enforcement_receipt_sha256',None)}[attack]
        q['capture_constraints'][key] = value
    elif attack == 'duration': c['end_time_ns'] = c['start_time_ns'] + 30000000001
    elif attack == 'negative_duration': c['end_time_ns'] = 119
    elif attack == 'future_capture': c['end_time_ns'] = 151
    elif attack == 'boolean_time': c['start_time_ns'] = True
    elif attack == 'combined_bytes': c['capture_bytes'] = 9
    elif attack == 'boolean_bytes': c['stderr_bytes'] = False
    elif attack == 'over_output': c.update(stdout_bytes=8388609, capture_bytes=8388609)
    elif attack == 'disk_exhausted': c['minimum_free_disk_bytes'] = 2147483647
    elif attack in ('timeout','truncated','exit'):
        c[{'timeout':'timed_out','truncated':'output_truncated','exit':'exit_code'}[attack]] = 1 if attack == 'exit' else True
    elif attack in ('tool','argv','capture_target','owner_receipt'):
        c[{'tool':'tool_sha256','argv':'exact_argv_manifest_sha256','capture_target':'target_identity_receipt_sha256',
           'owner_receipt':'private_owner_receipt_sha256'}[attack]] = '0'*64
    elif attack == 'capture_state': c['observation_state'] = 'EMPTY'
    elif attack == 'capture_duplicate': q['captures'].append(copy.deepcopy(c))
    elif attack == 'capture_missing': q['captures'].pop()
    elif attack == 'capture_extra': c['raw_stdout'] = 'PRIVATE_CANARY'
    elif attack == 'raw_private': q['private_evidence']['raw_path'] = 'PRIVATE_CANARY'
    elif attack in ('delivery','acl','storage_root'):
        q['private_evidence'][{'delivery':'delivery_receipt_sha256','acl':'acl_scope_receipt_sha256','storage_root':'evidence_root_sha256'}[attack]] = '0'*64
    elif attack == 'missing_encryption': q['private_evidence']['encryption_and_key_custody_receipt_sha256'] = None
    elif attack == 'same_reviewer': q['private_evidence']['reviewer_identity_sha256'] = q['private_evidence']['owner_identity_sha256']
    elif attack == 'empty_required': e['facts']['host_identity'].update(capture_state='EMPTY', observed=[]); c['observation_state']='EMPTY'
    elif attack == 'required_property': e['facts']['host_identity']['observed'] = {'other': 1}
    elif attack == 'unknown_qualification': q['unknown'] = True
    elif attack == 'boolean_version': q['version'] = True
    elif attack == 'protected_target': e['target']['label'] = 'pC4.example'
    elif attack == 'missing_group': del e['facts']['host_identity']
    # Keep redundant captures coherent except in the explicit divergence test below.
    e['command_captures'] = copy.deepcopy(q['captures'])
    publish()
    with pytest.raises(ValueError): verify()


def test_evidence_capture_substitution_rejected(tmp_path):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    e['command_captures'][0]['tool_sha256'] = '0'*64
    publish()
    with pytest.raises(ValueError): verify()


def test_empty_listener_is_valid_but_never_admission(tmp_path):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    e['facts']['tcp_and_udp_ports'].update(capture_state='EMPTY', observed=[])
    q['captures'][7]['observation_state'] = 'EMPTY'
    e['command_captures'] = copy.deepcopy(q['captures'])
    publish()
    assert verify()['status'] == 'BLOCKED'


def test_repeated_verification_never_consumes_nonce_or_claims_replay_protection(tmp_path):
    *_, verify, args = fixture(tmp_path)
    before = (tmp_path / 'replay.json').read_bytes()
    for _ in range(2):
        result = verify()
        assert result['status'] == 'BLOCKED' and result['replay_protection'] == 'NOT_IMPLEMENTED_NO_ADMISSION'
    assert (tmp_path / 'replay.json').read_bytes() == before


@pytest.mark.parametrize('name', ['qualification', 'evidence', 'manifest', 'policy', 'trust_store', 'review_policy', 'replay'])
def test_all_external_pins_required(tmp_path, name):
    *_, verify, args = fixture(tmp_path)
    with pytest.raises(ValueError): verify(**{name+'_sha256': '0'*64})


def test_report_does_not_echo_private_claims(tmp_path):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    for role in ('owner', 'provider'):
        old = m[role+'_id']; new = 'PRIVATE_CANARY_'+role
        q['identity'][role+'_id'] = m[role+'_id'] = bp[role+'_id'] = new
        for key in trust['keys']:
            if key['producer_id'] == old: key['producer_id'] = new
    publish()
    assert 'PRIVATE_CANARY' not in json.dumps(verify())


def test_qualification_cli_is_blocked_and_packaged(tmp_path, capsys):
    from strattester.research_cli import main
    from strattester.research.financial_test_package import RESEARCH_MODULES
    *_, verify, args = fixture(tmp_path)
    a = args(); v = a.pop('verifier'); now = a.pop('now_ns')
    argv = ['verify-g0-qualification', '--verification-time-ns', str(now),
            '--openssl-exe', str(v.executable), '--openssl-sha256', v.executable_sha256,
            '--scratch-root', str(tmp_path)]
    for name, value in a.items():
        flag = name[:-5] if name.endswith('_path') else name
        argv.extend(['--'+flag.replace('_','-'), str(value)])
    assert main(argv) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['contract_verified'] is True and report['status'] == 'BLOCKED'
    assert report['physical_g1'] == 'NOT_AUTHORIZED' and report['trading'] == 'NO-GO'
    assert 'financial_g0_qualification' in RESEARCH_MODULES


def test_cli_private_error_is_sanitized(tmp_path, capsys):
    from strattester.research_cli import main
    *_, verify, args = fixture(tmp_path)
    a = args(); v = a.pop('verifier'); now = a.pop('now_ns')
    a['qualification_path'] = str(tmp_path/'PRIVATE_CANARY_MISSING.json')
    argv = ['verify-g0-qualification', '--verification-time-ns', str(now),
            '--openssl-exe', str(v.executable), '--openssl-sha256', v.executable_sha256,
            '--scratch-root', str(tmp_path)]
    for name, value in a.items():
        flag = name[:-5] if name.endswith('_path') else name
        argv.extend(['--'+flag.replace('_','-'), str(value)])
    assert main(argv) == 2
    output = capsys.readouterr().out
    assert 'PRIVATE_CANARY' not in output
    assert json.loads(output)['status'] == 'BLOCKED'


@pytest.mark.parametrize('field,value', [
    ('observation_states', []), ('required_private_bindings', {}), ('stop_conditions', 'PRIVATE_CANARY'),
])
def test_manifest_metadata_has_strict_container_schemas(tmp_path, field, value):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    e[field] = value
    publish()
    with pytest.raises(ValueError): verify()


def test_replay_receipt_hash_reuse_rejected_even_with_changed_nonce(tmp_path):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    replay['entries'] = [dict(nonce_sha256='0'*64, vm_identity_sha256='0'*64,
                             receipt_sha256=pin(json.loads((tmp_path/'receipt.json').read_bytes())))]
    publish()
    with pytest.raises(ValueError): verify()


def test_library_missing_private_input_does_not_expose_path(tmp_path):
    *_, verify, args = fixture(tmp_path)
    with pytest.raises(ValueError) as error:
        verify(qualification_path=str(tmp_path/'PRIVATE_CANARY_MISSING.json'))
    assert 'PRIVATE_CANARY' not in str(error.value)


@pytest.mark.parametrize('name,limit', [('qualification',128*1024),('evidence',128*1024),
    ('manifest',64*1024),('policy',32*1024),('trust_store',64*1024),('review_policy',32*1024),('replay',128*1024)])
def test_each_explicit_document_byte_budget(tmp_path, name, limit):
    q, e, r, replay, m, bp, trust, publish, verify, args = fixture(tmp_path)
    a = args(); path = Path(a[name+'_path']); data = b' '*(limit+1)
    path.write_bytes(data)
    new_pin = sha256(data).hexdigest()
    if name != 'review_policy':
        r['expected'][name+'_sha256'] = new_pin
        (tmp_path/'review.json').write_bytes(encoded(r))
    with pytest.raises(ValueError): verify(**{name+'_sha256':new_pin})


@pytest.mark.parametrize('delta,valid', [(30000000000,True),(30000000001,False)])
def test_capture_wall_boundary_within_otherwise_valid_signed_window(tmp_path, delta, valid):
    q, e, r, replay, m, bp, trust, publish, verify, _ = fixture(tmp_path)
    m.update(issued_at_ns=110000000000, expires_at_ns=190000000000)
    bp.update(valid_from_ns=100000000000, valid_until_ns=200000000000)
    r.update(valid_from_ns=100000000000, valid_until_ns=200000000000, maximum_replay_age_ns=30000000000)
    replay['observed_at_ns'] = 140000000000
    for capture in q['captures']:
        capture.update(start_time_ns=120000000000, end_time_ns=120000000000+delta)
    e['command_captures'] = copy.deepcopy(q['captures'])
    publish()
    if valid: assert verify(now_ns=160000000000)['contract_verified'] is True
    else:
        with pytest.raises(ValueError): verify(now_ns=160000000000)
