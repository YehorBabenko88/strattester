"""Independent trust-policy tests; no native broker or production operations."""
import base64
from hashlib import sha256
import subprocess

import pytest

from strattester.research.financial_signatures import OpenSSLVerifier, load_trust_store
from strattester.research.financial_snapshot import canonical_bytes


def row(key_id='old', **changes):
    value = dict(key_id=key_id, producer_id='producer', public_key_b64=base64.b64encode(bytes(32)).decode(),
                 valid_from_ns=10, valid_until_ns=20, revoked=False)
    value.update(changes)
    return value


def provision(tmp_path, rows):
    data = canonical_bytes(dict(version=1, keys=rows))
    path = tmp_path / 'trust.json'
    path.write_bytes(data)
    return path, sha256(data).hexdigest()


def test_rotation_requires_external_repin_and_scoped_key_selection(tmp_path):
    path, old_pin = provision(tmp_path, [row()])
    original = load_trust_store(path, old_pin)
    path, new_pin = provision(tmp_path, [row(revoked=True), row('new', valid_from_ns=20, valid_until_ns=30)])
    with pytest.raises(ValueError, match='SHA256'):
        load_trust_store(path, old_pin)
    rotated = load_trust_store(path, new_pin)
    # Loaded policy is a snapshot; provisioning a new file cannot revoke an
    # already loaded instance. Operators must replace active instances too.
    assert original.key('producer', 'old', 20) == bytes(32)
    with pytest.raises(ValueError, match='revoked'):
        rotated.key('producer', 'old', 20)
    assert rotated.key('producer', 'new', 20) == bytes(32)
    assert rotated.key('producer', 'new', 30) == bytes(32)
    for producer, key, when in [('other', 'new', 20), ('producer', 'new', 19), ('producer', 'new', 31)]:
        with pytest.raises(ValueError):
            rotated.key(producer, key, when)


def test_duplicate_scoped_key_rejected_even_when_validity_windows_differ(tmp_path):
    path, pin = provision(tmp_path, [row(), row(valid_from_ns=21, valid_until_ns=30)])
    with pytest.raises(ValueError, match='duplicate'):
        load_trust_store(path, pin)


def test_pin_mismatch_prevents_any_executable_launch(tmp_path, monkeypatch):
    executable = tmp_path / 'inert-verifier'
    executable.write_bytes(b'not executable; measurement fixture only')
    def forbidden(*args, **kwargs):
        pytest.fail('an unpinned executable reached launch')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(ValueError, match='SHA256'):
        OpenSSLVerifier(executable, '0' * 64, tmp_path).verify(bytes(32), b'm', bytes(64))


@pytest.mark.parametrize('failure', [OSError('unavailable'), subprocess.TimeoutExpired('fixture', 5)])
def test_launch_failure_fails_closed_and_removes_scratch(tmp_path, monkeypatch, failure):
    executable = tmp_path / 'inert-verifier'
    executable.write_bytes(b'measurement fixture; never launched')
    def unavailable(*args, **kwargs):
        raise failure
    monkeypatch.setattr(subprocess, 'run', unavailable)
    with pytest.raises(ValueError, match='unavailable/timeout'):
        OpenSSLVerifier(executable, sha256(executable.read_bytes()).hexdigest(), tmp_path).verify(bytes(32), b'm', bytes(64))
    assert list(tmp_path.glob('ed25519-*')) == []
