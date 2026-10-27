"""Reject weak public keys, never infer authority from a valid curve point."""
import base64
import json
from hashlib import sha256
from pathlib import Path
import runpy

import pytest

BAD_KEYS=[b'\x01'+bytes(31),bytes(32),(2**255-20).to_bytes(32,'little'),
          (2**255-19).to_bytes(32,'little'),(2**255-18).to_bytes(32,'little'),bytes([255])*32,
          bytes.fromhex('98519eadf35b995233b51b5cd23e9cc5a28b639b5a4af0ec903cb960d81b7819')]


@pytest.mark.parametrize('message',[b'no private key possession',b'other domain'])
def test_identity_forgery_rejected_before_signature_assurance(tmp_path,message):
    factory=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))['verifier']
    verifier=factory(tmp_path)
    with pytest.raises(ValueError,match='Ed25519 public key'):
        verifier.verify(BAD_KEYS[0],message,b'\x01'+bytes(63))


@pytest.mark.parametrize('public',BAD_KEYS)
def test_unusable_pinned_key_rejected_at_trust_store_intake(tmp_path,public):
    from strattester.research.financial_signatures import load_trust_store
    payload=dict(version=1,keys=[dict(key_id='external',producer_id='owner',
        public_key_b64=base64.b64encode(public).decode(),valid_from_ns=0,valid_until_ns=100,revoked=False)])
    data=json.dumps(payload).encode();path=tmp_path/'trust.json';path.write_bytes(data)
    with pytest.raises(ValueError,match='Ed25519 public key'):
        load_trust_store(path,sha256(data).hexdigest())


def test_normal_key_signature_interoperates_between_independent_backends(tmp_path):
    from nacl.signing import SigningKey
    factory=runpy.run_path(str(Path(__file__).with_name('test_financial_signatures.py')))['verifier']
    key=SigningKey.generate();message=b'SOFTWARE_ONLY_NO_AUTHORITY'
    assert factory(tmp_path).verify(bytes(key.verify_key),message,key.sign(message).signature) is True


@pytest.mark.parametrize('broken',['always_true','always_false','old_mixed_order','unavailable'])
def test_backend_failure_or_old_subgroup_semantics_never_fall_back(monkeypatch,broken):
    import nacl.bindings
    from strattester.research.financial_signatures import validate_ed25519_public_key
    original=nacl.bindings.crypto_core_ed25519_is_valid_point
    mixed=BAD_KEYS[-1]
    def changed(point):
        if broken=='unavailable':raise RuntimeError('backend missing')
        if broken=='always_true':return True
        if broken=='always_false':return False
        return True if point==mixed else original(point)
    monkeypatch.setattr(nacl.bindings,'crypto_core_ed25519_is_valid_point',changed)
    with pytest.raises(ValueError,match='Ed25519 public key validator'):
        validate_ed25519_public_key(bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'))
