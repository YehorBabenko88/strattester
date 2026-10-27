"""Adversarial G0 assertion verification, never target admission or execution.

The signing domain, field roster and serialization below are independent of
production constants. Keys are fresh software-only keys in pytest scratch.
Each attack first verifies a real two-signature control, so rejection cannot be
explained by an unusable fixture. No VM, provider or physical receipt is read.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from strattester.research.financial_g0_receipt import verify_g0_receipt
from strattester.research.financial_signatures import OpenSSLVerifier


WIRE_DOMAIN = b'STRATTESTER_G0_TARGET_BINDING_V1\x00'
FIELDS = (
    'source_sha', 'tree_sha', 'package_sha256', 'command_manifest_sha256',
    'vm_identity_sha256', 'provider_identity_sha256', 'sandbox_root_sha256',
    'evidence_root_sha256', 'snapshot_generation_sha256', 'rollback_receipt_sha256',
    'private_delivery_receipt_sha256', 'capture_controls_receipt_sha256',
    'acl_scope_receipt_sha256', 'tool_roster_sha256', 'evidence_manifest_sha256',
)
ROLES = ('owner', 'provider')


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def assert_blocked(result):
    assert result['signatures_verified'] is True
    assert result['status'] == 'BLOCKED'
    assert result['target_truth'] == 'NOT_ESTABLISHED_BY_SIGNATURE'
    assert result['replay_protection'] == 'NOT_IMPLEMENTED_NO_ADMISSION'
    assert set(result['blockers']) >= {
        'INDEPENDENT_FACT_AND_RECEIPT_REVIEW_REQUIRED',
        'DURABLE_REPLAY_REGISTRY_REQUIRED', 'G0_ADMISSION_NOT_IMPLEMENTED',
    }
    assert result['physical_g0'] == 'PLAN_READY_TARGET_EVIDENCE_BLOCKED'
    for field in ('physical_g1', 'g1_execute', 'g1_cleanup'):
        assert result[field] == 'NOT_AUTHORIZED'
    assert result['deployment'] == result['trading'] == 'NO-GO'


class Receipt:
    def __init__(self, root):
        self.root = root
        found = shutil.which('openssl')
        executable = Path(found or 'C:/Program Files/Git/usr/bin/openssl.exe').resolve()
        assert executable.is_file(), 'Real Ed25519 dependency required; do not skip'
        self.verifier = OpenSSLVerifier(executable, sha256(executable.read_bytes()).hexdigest(), root)
        (root / 'openssl.cnf').write_bytes(b'')
        self.env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR') if k in os.environ}
        self.env['OPENSSL_CONF'] = str(root / 'openssl.cnf')
        self.policy = dict(
            version=1, purpose='G0_BINDING_VERIFICATION_POLICY',
            expected={f: sha256(f.encode()).hexdigest()[:40 if f in ('source_sha', 'tree_sha') else 64]
                      for f in FIELDS},
            owner_id='independent-owner', provider_id='independent-provider',
            owner_key_id='owner-key', provider_key_id='provider-key',
            valid_from_ns=100, valid_until_ns=200,
        )
        self.manifest = dict(
            version=1, purpose='G0_READ_ONLY_BINDING_RECEIPT', binding=deepcopy(self.policy['expected']),
            **{f: self.policy[f] for role in ROLES for f in (role+'_id', role+'_key_id')},
            issued_at_ns=110, expires_at_ns=190, nonce='c'*64,
        )
        self.trust = dict(version=1, keys=[])
        for role in ROLES:
            private = root / (role+'.der')
            self.openssl('genpkey', '-algorithm', 'ED25519', '-outform', 'DER', '-out', private)
            public = self.openssl('pkey', '-inform', 'DER', '-in', private, '-pubout', '-outform', 'DER')
            assert public[:12] == bytes.fromhex('302a300506032b6570032100') and len(public) == 44
            self.trust['keys'].append(dict(
                producer_id=self.policy[role+'_id'], key_id=self.policy[role+'_key_id'],
                public_key_b64=base64.b64encode(public[12:]).decode(),
                valid_from_ns=100, valid_until_ns=200, revoked=False,
            ))
        self.publish()

    def openssl(self, *args):
        return subprocess.run(
            [str(self.verifier.executable), *map(str, args)], cwd=self.root, env=self.env,
            stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=5,
        ).stdout

    def publish(self, domain=WIRE_DOMAIN):
        (self.root / 'message').write_bytes(domain+wire(self.manifest))
        signatures = {}
        for role in ROLES:
            self.openssl('pkeyutl', '-sign', '-rawin', '-keyform', 'DER', '-inkey',
                         self.root / (role+'.der'), '-in', self.root / 'message',
                         '-out', self.root / (role+'.sig'))
            signatures[role] = base64.b64encode((self.root / (role+'.sig')).read_bytes()).decode()
        self.receipt = dict(self.manifest, signatures=signatures)
        self.write('manifest', self.receipt)
        self.write('policy', self.policy)
        self.write('trust_store', self.trust)

    def write(self, name, payload):
        (self.root / (name+'.json')).write_bytes(wire(payload))

    def pins(self):
        return {name+'_sha256': sha256((self.root / (name+'.json')).read_bytes()).hexdigest()
                for name in ('manifest', 'policy', 'trust_store')}

    def verify(self, **changes):
        args = {name+'_path': str(self.root / (name+'.json'))
                for name in ('manifest', 'policy', 'trust_store')}
        return verify_g0_receipt(**{**args, **self.pins(), 'verifier': self.verifier,
                                    'now_ns': 150, **changes})


@pytest.fixture
def receipt(tmp_path):
    r = Receipt(tmp_path)
    assert_blocked(r.verify())
    return r


@pytest.mark.parametrize('field', FIELDS)
def test_each_resigned_binding_requires_unchanged_external_policy(receipt, field):
    # Removing any equality check must expose a validly signed substitution.
    receipt.manifest['binding'][field] = '0'*len(receipt.manifest['binding'][field])
    receipt.publish()
    with pytest.raises(ValueError, match='pinned binding'):
        receipt.verify()


@pytest.mark.parametrize('field', FIELDS)
def test_every_binding_is_covered_by_both_signature_messages(receipt, field):
    # Even replacing the external policy cannot repair unsigned receipt edits.
    replacement = '0'*len(receipt.manifest['binding'][field])
    receipt.receipt['binding'][field] = replacement
    receipt.policy['expected'][field] = replacement
    receipt.write('manifest', receipt.receipt)
    receipt.write('policy', receipt.policy)
    with pytest.raises(ValueError, match='Ed25519'):
        receipt.verify()


@pytest.mark.parametrize('role', ROLES)
def test_missing_signature_is_not_one_authority_approval(receipt, role):
    del receipt.receipt['signatures'][role]
    receipt.write('manifest', receipt.receipt)
    with pytest.raises(ValueError, match='schema'):
        receipt.verify()


@pytest.mark.parametrize('domain', [
    b'', b'STRATTESTER_G0_TARGET_BINDING_V1', b'STRATTESTER_G0_TARGET_BINDING_V1\x00\x00',
    b'STRATTESTER_PHYSICAL_G1_OWNER_V1\x00', b'STRATTESTER_GRID_EXPORT_V1\x00',
])
def test_cross_protocol_signatures_cannot_verify_as_g0(receipt, domain):
    receipt.publish(domain=domain)
    with pytest.raises(ValueError, match='Ed25519'):
        receipt.verify()


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('attack', ['revoked', 'not_yet_valid_at_issue', 'expired_now', 'unknown_key', 'wrong_identity'])
def test_both_authorities_require_scoped_current_and_issuance_validity(receipt, role, attack):
    key = receipt.trust['keys'][ROLES.index(role)]
    if attack == 'revoked': key['revoked'] = True
    elif attack == 'not_yet_valid_at_issue': key['valid_from_ns'] = 111
    elif attack == 'expired_now': key['valid_until_ns'] = 149
    elif attack == 'unknown_key': key['key_id'] += '-substitute'
    else: key['producer_id'] += '-substitute'
    receipt.publish()
    with pytest.raises(ValueError, match='producer'):
        receipt.verify()


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('interval', [(110, 150), (111, 200), (100, 149)])
def test_key_validity_endpoints_are_checked_for_each_role(receipt, role, interval):
    key = receipt.trust['keys'][ROLES.index(role)]
    key['valid_from_ns'], key['valid_until_ns'] = interval
    receipt.publish()
    if interval == (110, 150):
        assert_blocked(receipt.verify())
    else:
        with pytest.raises(ValueError, match='expired'):
            receipt.verify()


@pytest.mark.parametrize('role', ROLES)
def test_one_valid_authority_never_masks_other_signature_failure(receipt, role):
    receipt.receipt['signatures'][role] = base64.b64encode(bytes(64)).decode()
    receipt.write('manifest', receipt.receipt)
    with pytest.raises(ValueError, match='Ed25519'):
        receipt.verify()


@pytest.mark.parametrize('field', ['owner_id', 'provider_id', 'owner_key_id', 'provider_key_id'])
def test_resigning_cannot_rebind_authority_identity(receipt, field):
    receipt.manifest[field] += '-alias'
    receipt.publish()
    with pytest.raises(ValueError, match='pinned binding'):
        receipt.verify()


@pytest.mark.parametrize('name', ['manifest', 'policy', 'trust_store'])
def test_candidate_cannot_replace_external_byte_pin(receipt, name):
    old_pins = receipt.pins()
    # Whitespace preserves JSON semantics and valid signatures but changes bytes.
    path = receipt.root / (name+'.json')
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='SHA256'):
        receipt.verify(**old_pins)
    assert_blocked(receipt.verify())


@pytest.mark.parametrize('name', ['manifest', 'policy', 'trust_store'])
@pytest.mark.parametrize('attack', ['duplicate', 'nonfinite', 'deep', 'truncated'])
def test_repinned_malformed_inputs_still_fail_closed(receipt, name, attack):
    path = receipt.root / (name+'.json')
    if attack == 'duplicate': data = path.read_bytes().replace(b'{', b'{"version":1,', 1)
    elif attack == 'nonfinite': data = b'{"version":1e309}'
    elif attack == 'deep': data = b'{"x":'+b'['*65+b'0'+b']'*65+b'}'
    else: data = path.read_bytes()[:-1]
    path.write_bytes(data)
    with pytest.raises(ValueError):
        receipt.verify()


@pytest.mark.parametrize('nonce', ['', 'a'*63, 'a'*65, 'G'*64, None, True])
def test_signed_malformed_nonce_does_not_establish_freshness(receipt, nonce):
    receipt.manifest['nonce'] = nonce
    receipt.publish()
    with pytest.raises(ValueError, match='digest'):
        receipt.verify()


def test_nonce_is_signed_but_not_a_durable_challenge_claim(receipt):
    receipt.receipt['nonce'] = 'd'*64
    receipt.write('manifest', receipt.receipt)
    with pytest.raises(ValueError, match='Ed25519'):
        receipt.verify()
    receipt.manifest['nonce'] = 'd'*64
    receipt.publish()
    for _ in range(2):
        assert_blocked(receipt.verify())


def test_revocation_rollback_under_current_pin_is_rejected(receipt):
    old_trust = (receipt.root / 'trust_store.json').read_bytes()
    receipt.trust['keys'][1]['revoked'] = True
    receipt.publish()
    current_pins = receipt.pins()
    with pytest.raises(ValueError, match='revoked'):
        receipt.verify(**current_pins)
    (receipt.root / 'trust_store.json').write_bytes(old_trust)
    with pytest.raises(ValueError, match='SHA256'):
        receipt.verify(**current_pins)
    # Restoring the caller's old pin too cannot be detected without external
    # monotonic state. It must never become a successful admission.
    assert_blocked(receipt.verify())


def test_coherent_old_snapshot_replay_and_clock_rollback_never_admit(receipt):
    old_bytes = {n: (receipt.root / (n+'.json')).read_bytes()
                 for n in ('manifest', 'policy', 'trust_store')}
    old_pins = receipt.pins()
    for field in ('snapshot_generation_sha256', 'rollback_receipt_sha256'):
        receipt.policy['expected'][field] = receipt.manifest['binding'][field] = 'e'*64
    receipt.manifest.update(issued_at_ns=151, expires_at_ns=190, nonce='f'*64)
    receipt.publish()
    current_pins = receipt.pins()
    assert_blocked(receipt.verify(now_ns=160))
    for name, data in old_bytes.items():
        (receipt.root / (name+'.json')).write_bytes(data)
    with pytest.raises(ValueError, match='SHA256'):
        receipt.verify(**current_pins)
    assert_blocked(receipt.verify(**old_pins, now_ns=150))
    assert_blocked(receipt.verify(**old_pins, now_ns=150))


@pytest.mark.parametrize('attack', ['duplicate_scope', 'shared_public', 'same_authority'])
def test_aliasing_cannot_create_two_independent_authorities(receipt, attack):
    if attack == 'duplicate_scope':
        receipt.trust['keys'].append(deepcopy(receipt.trust['keys'][0]))
    elif attack == 'shared_public':
        receipt.trust['keys'][1]['public_key_b64'] = receipt.trust['keys'][0]['public_key_b64']
        # Both signatures must be valid under the shared key; otherwise crypto
        # failure would mask removal of the independent-authority guard.
        (receipt.root / 'provider.der').write_bytes((receipt.root / 'owner.der').read_bytes())
    else:
        receipt.manifest['provider_id'] = receipt.policy['provider_id'] = receipt.policy['owner_id']
        receipt.trust['keys'][1]['producer_id'] = receipt.policy['owner_id']
    receipt.publish()
    for role, key in zip(ROLES, receipt.trust['keys']):
        assert receipt.verifier.verify(
            base64.b64decode(key['public_key_b64']), WIRE_DOMAIN+wire(receipt.manifest),
            base64.b64decode(receipt.receipt['signatures'][role]),
        ) is True
    reason = {'duplicate_scope': 'duplicate trust key', 'shared_public': 'shared authority key',
              'same_authority': 'separate owner/provider'}[attack]
    with pytest.raises(ValueError, match=reason):
        receipt.verify()


@pytest.mark.parametrize('role', ROLES)
def test_pinned_degenerate_key_forgery_is_only_a_blocked_assertion(receipt, role):
    # Unresolved P2 characterization, NOT weak-key rejection coverage. Identity
    # public key and R=identity/S=0 need no private key. External provisioning of
    # this weak key is required; the candidate cannot bypass an unchanged pin.
    # signatures_verified must never be consumed as proof of key possession.
    key = receipt.trust['keys'][ROLES.index(role)]
    key['public_key_b64'] = base64.b64encode(b'\x01'+bytes(31)).decode()
    receipt.receipt['signatures'][role] = base64.b64encode(b'\x01'+bytes(63)).decode()
    receipt.write('trust_store', receipt.trust)
    receipt.write('manifest', receipt.receipt)
    assert_blocked(receipt.verify())


@pytest.mark.parametrize('attack', ['invalid_signature', 'missing_input', 'verifier_unavailable', 'valid'])
def test_cli_emits_blocked_exit_for_success_and_failure(receipt, capsys, attack):
    from strattester.research_cli import main
    if attack == 'invalid_signature':
        receipt.receipt['signatures']['provider'] = base64.b64encode(bytes(64)).decode()
        receipt.write('manifest', receipt.receipt)
    args = ['verify-g0-receipt', '--verification-time-ns', '150',
            '--openssl-exe', str(receipt.verifier.executable),
            '--openssl-sha256', receipt.verifier.executable_sha256,
            '--scratch-root', str(receipt.root)]
    pins = receipt.pins()
    for name in ('manifest', 'policy', 'trust_store'):
        flag = name.replace('_', '-')
        path = receipt.root / (name+'.json')
        args.extend(['--'+flag, str(path), '--'+flag+'-sha256', pins[name+'_sha256']])
    if attack == 'missing_input':
        (receipt.root / 'manifest.json').unlink()
    elif attack == 'verifier_unavailable':
        args[args.index('--openssl-exe')+1] = str(receipt.root / 'missing-openssl')
    assert main(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'BLOCKED'
    assert result['physical_g1'] == 'NOT_AUTHORIZED'
    if attack == 'valid':
        assert_blocked(result)
    else:
        assert result['code'] == 'RESEARCH_ERROR'
        assert result.get('signatures_verified') is not True
