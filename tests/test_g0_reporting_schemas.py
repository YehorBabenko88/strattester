"""Declarative reporting checks; no physical facts or admission are produced."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from tests.test_physical_g0_inventory_contract import collect

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT/'docs/readiness'
GROUPS = (
    'host_identity', 'os_and_powershell', 'python_base_and_venv',
    'torch_and_dependencies', 'cpu_ram_disk_and_limits', 'gpu_driver_and_cuda',
    'processes_and_services', 'tcp_and_udp_ports', 'acl_namespace_and_mounts',
    'source_and_database_ownership',
)
PROVIDERS = ('identity', 'os', 'cpu', 'disk', 'services', 'processes', 'tcp', 'udp', 'gpu', 'sandbox')
STATES = ('OBSERVED', 'EMPTY', 'MISSING', 'UNAVAILABLE', 'NOT_COLLECTED')


def validator(name):
    schema = json.loads((READINESS/'schemas'/name).read_bytes())
    Draft202012Validator.check_schema(schema)
    # Validation may resolve internal definitions only, never referenced paths/URLs.
    def refs(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == '$ref':
                    assert item.startswith('#/')
                else:
                    refs(item)
        elif isinstance(value, list):
            for item in value:
                refs(item)
    refs(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def manifest():
    return json.loads((READINESS/'TARGET_G0_EVIDENCE_MANIFEST.template.json').read_bytes())


def test_manifest_template_has_exact_ten_uncollected_groups():
    payload = manifest()
    validator('g0-evidence-manifest-v1.schema.json').validate(payload)
    assert set(payload['facts']) == set(GROUPS)
    for fact in payload['facts'].values():
        assert fact['capture_state'] == 'NOT_COLLECTED'
        assert all(value is None for key, value in fact.items() if key != 'capture_state')
    assert payload['command_captures'] is None
    assert payload['target']['label'] is None
    assert payload['execution_authorized'] is False


@pytest.mark.parametrize('group', GROUPS)
@pytest.mark.parametrize('state,value', [
    ('OBSERVED', {'synthetic_only': True}), ('EMPTY', []),
    ('MISSING', {'partial_synthetic_only': True}), ('UNAVAILABLE', None),
    ('NOT_COLLECTED', None),
])
def test_state_shapes_are_diagnostic_and_never_pass(tmp_path, group, state, value):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    payload = manifest()
    payload['facts'][group].update(capture_state=state, observed=value)
    validator('g0-evidence-manifest-v1.schema.json').validate(payload)
    path = tmp_path/'synthetic.json'
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    result = inspect_g0_evidence(str(path), hashlib.sha256(data).hexdigest())
    assert result['status'] == 'BLOCKED'
    assert set(result['groups']) == set(GROUPS)
    assert all(row['admission'] == 'BLOCKED' for row in result['groups'].values())
    assert result['physical_g1'] == 'NOT_AUTHORIZED'
    assert result['trading'] == 'NO-GO'


@pytest.mark.parametrize('state,value', [
    ('NOT_COLLECTED', []), ('NOT_COLLECTED', {}), ('UNAVAILABLE', []),
    ('EMPTY', None), ('EMPTY', [1]), ('MISSING', None), ('MISSING', {}),
    ('OBSERVED', None), ('OBSERVED', []), ('PASS', {'fake': True}),
])
def test_unknown_and_contradictory_states_are_rejected(state, value):
    payload = manifest()
    payload['facts']['host_identity'].update(capture_state=state, observed=value)
    with pytest.raises(ValidationError):
        validator('g0-evidence-manifest-v1.schema.json').validate(payload)


@pytest.mark.parametrize('mutation', ['version-bool', 'future-version', 'collector-bool',
    'future-contract', 'missing-group', 'extra-group', 'missing-field', 'extra-field',
    'collected-hash', 'fake-pass', 'g1', 'protected-target'])
def test_manifest_required_fields_versions_and_non_authorization(mutation):
    payload = manifest()
    if mutation == 'version-bool': payload['version'] = True
    elif mutation == 'future-version': payload['version'] = 2
    elif mutation == 'collector-bool': payload['collector_contract']['schema'] = True
    elif mutation == 'future-contract': payload['collector_contract']['observation_contract_version'] = 3
    elif mutation == 'missing-group': payload['facts'].pop('host_identity')
    elif mutation == 'extra-group': payload['facts']['extra'] = {}
    elif mutation == 'missing-field': payload['facts']['host_identity'].pop('observed')
    elif mutation == 'extra-field': payload['facts']['host_identity']['pass'] = True
    elif mutation == 'collected-hash': payload['facts']['host_identity']['owner_receipt_sha256'] = 'a'*64
    elif mutation == 'fake-pass': payload['physical_g0_readiness'] = 'PASS'
    elif mutation == 'g1': payload['physical_g1'] = 'AUTHORIZED'
    elif mutation == 'protected-target': payload['target']['label'] = 'PC4.example'
    with pytest.raises(ValidationError):
        validator('g0-evidence-manifest-v1.schema.json').validate(payload)


@pytest.mark.parametrize('group', GROUPS)
def test_unknown_receipt_fields_do_not_extend_the_contract(group):
    payload = manifest()
    payload['facts'][group]['unreviewed_sha256'] = None
    with pytest.raises(ValidationError):
        validator('g0-evidence-manifest-v1.schema.json').validate(payload)


def test_declarative_integer_semantics_do_not_replace_strict_json_inspection(tmp_path):
    from strattester.research.financial_g0_evidence import inspect_g0_evidence
    payload = manifest()
    payload['version'] = 1.0
    # JSON Schema's integer type includes mathematically integral JSON numbers.
    # The existing inspector additionally requires a Python int after parsing.
    validator('g0-evidence-manifest-v1.schema.json').validate(payload)
    path = tmp_path/'integral-float.json'
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    with pytest.raises(ValueError, match='non-authorizing envelope'):
        inspect_g0_evidence(str(path), hashlib.sha256(data).hexdigest())


@pytest.fixture(params=['powershell.exe', 'pwsh'], scope='module')
def mock_report(request, tmp_path_factory):
    # Existing harness replaces every inventory provider before running source.
    return collect(tmp_path_factory.mktemp('mock-report'), shell=request.param)


def test_powershell_mock_output_matches_declarative_contract(mock_report):
    validator('g0-observation-v2.schema.json').validate(mock_report)
    assert mock_report['schema'] == 1
    assert mock_report['observation_contract_version'] == 2
    assert set(mock_report['observations']) == set(PROVIDERS)
    assert mock_report['sandbox']['confinement_proven'] is False
    assert mock_report['g0_readiness'] == 'BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE'
    assert mock_report['g1'] == 'NOT_AUTHORIZED'


@pytest.mark.parametrize('provider', PROVIDERS)
def test_provider_not_collected_cannot_masquerade_as_collector_output(mock_report, provider):
    payload = copy.deepcopy(mock_report)
    payload['observations'][provider] = 'NOT_COLLECTED'
    with pytest.raises(ValidationError):
        validator('g0-observation-v2.schema.json').validate(payload)


@pytest.mark.parametrize('mutation', ['schema-bool', 'schema-new', 'contract-bool',
    'contract-new', 'missing-state', 'missing-policy', 'missing-payload', 'singleton',
    'null-empty', 'null-observed', 'partial-unavailable', 'missing-required-fact', 'pass'])
def test_collector_version_cardinality_and_missing_data_rejected(mock_report, mutation):
    payload = copy.deepcopy(mock_report)
    if mutation == 'schema-bool': payload['schema'] = True
    elif mutation == 'schema-new': payload['schema'] = 2
    elif mutation == 'contract-bool': payload['observation_contract_version'] = True
    elif mutation == 'contract-new': payload['observation_contract_version'] = 3
    elif mutation == 'missing-state': payload['observations'].pop('cpu')
    elif mutation == 'missing-policy': payload['observation_requirements'].pop('tcp')
    elif mutation == 'missing-payload': payload.pop('cpu')
    elif mutation == 'singleton': payload['cpu'] = payload['cpu'][0]
    elif mutation == 'null-empty': payload['observations']['tcp'] = 'EMPTY'; payload['listeners'] = None
    elif mutation == 'null-observed': payload['cpu'] = []
    elif mutation == 'partial-unavailable': payload['observations']['udp'] = 'UNAVAILABLE'
    elif mutation == 'missing-required-fact': payload['cpu'][0]['Name'] = None
    elif mutation == 'pass': payload['g0_readiness'] = 'PASS'
    with pytest.raises(ValidationError):
        validator('g0-observation-v2.schema.json').validate(payload)


@pytest.mark.parametrize('shell', ['powershell.exe', 'pwsh'])
@pytest.mark.parametrize('overrides,source,state', [
    ('function Get-NetTCPConnection {}; function Get-NetUDPEndpoint {}', 'udp', 'EMPTY'),
    ('function Get-CimInstance {param($ClassName,$Filter)}', 'identity', 'EMPTY'),
    ("function Get-Service {[pscustomobject]@{Name='fixture';Status='Running'}}", 'services', 'MISSING'),
    ("function Get-NetUDPEndpoint {[pscustomobject]@{LocalPort=42;OwningProcess=7;LocalAddress='::'}; Write-Error 'secret-DSN'}", 'udp', 'UNAVAILABLE'),
])
def test_mocked_absence_partial_and_error_outputs_keep_their_states(tmp_path, shell, overrides, source, state):
    report = collect(tmp_path, shell=shell, overrides=overrides)
    validator('g0-observation-v2.schema.json').validate(report)
    assert report['observations'][source] == state
    assert report['g0_readiness'].startswith('BLOCKED')
    assert report['g1'] == 'NOT_AUTHORIZED'


def test_report_template_preserves_all_ten_groups_and_no_target_selection():
    text = (READINESS/'G0_FINAL_REPORT.template.md').read_text(encoding='utf-8')
    for group in GROUPS:
        assert f'| `{group}` | NOT_COLLECTED | null | BLOCKED |' in text
    selection = json.loads((READINESS/'TARGET_G0_SELECTION_STATUS.json').read_bytes())
    assert selection['vm_selection'] == 'NOT_SELECTED'
    assert selection['physical_collection_executed'] is False
