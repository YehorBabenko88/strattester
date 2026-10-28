"""Software inspection never substitutes for target attestation."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[2] / 'docs/readiness/TARGET_G0_EVIDENCE_MANIFEST.template.json'


def inspect(tmp_path, payload):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    data = json.dumps(payload).encode()
    path = tmp_path / 'manifest.json'
    path.write_bytes(data)
    return inspect_g0_evidence(str(path), hashlib.sha256(data).hexdigest())


def test_template_cannot_authorize_any_group(tmp_path):
    result = inspect(tmp_path, json.loads(TEMPLATE.read_text()))
    assert result['status'] == 'BLOCKED'
    assert len(result['groups']) == 10
    assert all(v['admission'] == 'BLOCKED' for v in result['groups'].values())
    assert result['physical_g1'] == 'NOT_AUTHORIZED'


@pytest.mark.parametrize('state,value', [('OBSERVED', {'fake': 'receipt'}), ('EMPTY', []),
    ('MISSING', {'partial': True}), ('UNAVAILABLE', None), ('NOT_COLLECTED', None)])
def test_all_self_reported_states_remain_blocked(tmp_path, state, value):
    payload = json.loads(TEMPLATE.read_text())
    for fact in payload['facts'].values():
        fact['capture_state'] = state
        fact['observed'] = value
        if state != 'NOT_COLLECTED':
            for key in fact.keys() - {'capture_state', 'observed'}:
                fact[key] = 'a' * 64
    result = inspect(tmp_path, payload)
    assert result['status'] == 'BLOCKED'
    assert all(v['admission'] == 'BLOCKED' for v in result['groups'].values())
    assert 'fake' not in json.dumps(result)


@pytest.mark.parametrize('mutation', ['boolean_version', 'missing_group', 'unknown_group',
    'pass_claim', 'authorized', 'protected_target', 'not_collected_with_receipt', 'empty_with_rows'])
def test_malformed_or_authorizing_claims_fail_closed(tmp_path, mutation):
    p = copy.deepcopy(json.loads(TEMPLATE.read_text()))
    if mutation == 'boolean_version': p['version'] = True
    elif mutation == 'missing_group': p['facts'].pop('host_identity')
    elif mutation == 'unknown_group': p['facts']['other'] = {}
    elif mutation == 'pass_claim': p['physical_g0_readiness'] = 'PASS'
    elif mutation == 'authorized': p['execution_authorized'] = True
    elif mutation == 'protected_target': p['target']['label'] = 'LS5.example'
    elif mutation == 'not_collected_with_receipt': p['facts']['host_identity']['owner_receipt_sha256'] = 'a' * 64
    elif mutation == 'empty_with_rows': p['facts']['host_identity'].update(capture_state='EMPTY', observed=[1])
    with pytest.raises(ValueError): inspect(tmp_path, p)


def test_external_pin_and_duplicate_json_rejected(tmp_path):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    path = tmp_path / 'manifest.json'
    path.write_bytes(b'{"version":1,"version":1}')
    with pytest.raises(ValueError, match='SHA256'): inspect_g0_evidence(str(path), '0' * 64)
    with pytest.raises(ValueError, match='duplicate'): inspect_g0_evidence(str(path), hashlib.sha256(path.read_bytes()).hexdigest())


def test_cli_is_non_authorizing(tmp_path, capsys):
    from strattester.research_cli import main
    data = TEMPLATE.read_bytes()
    path = tmp_path / 'manifest.json'
    path.write_bytes(data)
    assert main(['inspect-g0-evidence', '--manifest', str(path), '--manifest-sha256', hashlib.sha256(data).hexdigest()]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'BLOCKED'


@pytest.mark.parametrize('value', [[], {}, True, 2, None])
def test_collector_state_malformed_types_rejected(tmp_path, value):
    payload = json.loads(TEMPLATE.read_text())
    payload['collector_contract']['capture_state'] = value
    with pytest.raises(ValueError): inspect(tmp_path, payload)


def test_no_referenced_artifact_execution_or_external_io(tmp_path, monkeypatch):
    import socket
    import sqlite3
    import subprocess
    from strattester.research import financial_g0_evidence as module
    from strattester.research.financial_test_package import RESEARCH_MODULES
    assert 'financial_g0_evidence' in RESEARCH_MODULES
    payload = json.loads(TEMPLATE.read_text())
    payload['command_captures'] = {'path': 'DO_NOT_OPEN', 'command': 'DO_NOT_EXECUTE'}
    real_read = module.verified_bytes
    calls = []
    def read(*args):
        calls.append(args[0])
        return real_read(*args)
    def forbidden(*args, **kwargs): raise AssertionError('unexpected external IO')
    monkeypatch.setattr(module, 'verified_bytes', read)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert inspect(tmp_path, payload)['status'] == 'BLOCKED'
    assert calls == [str(tmp_path / 'manifest.json')]
    assert list(tmp_path.iterdir()) == [tmp_path / 'manifest.json']


@pytest.mark.parametrize('token', ['1e309', '-1e999', '9.99e9999'])
@pytest.mark.parametrize('location', ['observed', 'command_captures', 'description'])
def test_overflow_json_numbers_rejected_before_claim_inspection(tmp_path, token, location):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    payload = json.loads(TEMPLATE.read_text())
    if location == 'observed':
        payload['facts']['host_identity'].update(capture_state='OBSERVED', observed={'number': 'EXPONENT'})
    elif location == 'command_captures':
        payload['command_captures'] = {'untrusted': 'EXPONENT'}
    else:
        payload['stop_conditions'] = ['EXPONENT']
    data = json.dumps(payload).encode().replace(b'"EXPONENT"', token.encode())
    path = tmp_path / 'overflow.json'
    path.write_bytes(data)
    with pytest.raises(ValueError, match='nonfinite'):
        inspect_g0_evidence(str(path), hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize('token', ['1e308', '-1e308', '1e-9999'])
def test_finite_extremes_do_not_create_admission(tmp_path, token):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    payload = json.loads(TEMPLATE.read_text())
    payload['facts']['host_identity'].update(capture_state='OBSERVED', observed={'number': 'EXPONENT'})
    data = json.dumps(payload).encode().replace(b'"EXPONENT"', token.encode())
    path = tmp_path / 'finite.json'
    path.write_bytes(data)
    result = inspect_g0_evidence(str(path), hashlib.sha256(data).hexdigest())
    assert result['status'] == 'BLOCKED'
    assert all(g['admission'] == 'BLOCKED' for g in result['groups'].values())
