"""Independent RFC8032 vectors, no producer signing helper in verifier tests."""
import base64
from hashlib import sha256
from pathlib import Path
import shutil
import pytest
from strattester.research.financial_snapshot import canonical_bytes

PUBLIC=bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
SIGNATURE=bytes.fromhex('92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00')

def openssl_path():
    found=shutil.which('openssl')
    p=Path(found) if found else Path('C:/Program Files/Git/usr/bin/openssl.exe')
    assert p.is_file(),'Mandatory real OpenSSL dependency unavailable; not a skipped crypto test'
    return p.resolve()


def verifier(tmp_path):
    from strattester.research.financial_signatures import OpenSSLVerifier
    p=openssl_path()
    return OpenSSLVerifier(p,sha256(p.read_bytes()).hexdigest(),tmp_path)


def test_rfc8032_vector2_real_independent_verifier(tmp_path):
    assert verifier(tmp_path).verify(PUBLIC,b'\x72',SIGNATURE) is True

@pytest.mark.parametrize('message,signature',[(b'\x73',SIGNATURE),(b'\x72',bytes(64)),(b'\x72',SIGNATURE[:-1])])
def test_signature_or_message_mutation_rejects(tmp_path,message,signature):
    with pytest.raises(ValueError):verifier(tmp_path).verify(PUBLIC,message,signature)


def test_verifier_identity_is_not_selected_by_artifact(tmp_path):
    from strattester.research.financial_signatures import OpenSSLVerifier
    with pytest.raises(ValueError):OpenSSLVerifier(openssl_path(),'0'*64,tmp_path).verify(PUBLIC,b'\x72',SIGNATURE)


def test_signature_input_budget_precedes_subprocess(tmp_path,monkeypatch):
    import subprocess
    def denied(*a,**k):raise AssertionError('subprocess must not run')
    monkeypatch.setattr(subprocess,'run',denied)
    with pytest.raises(ValueError,match='budget'):verifier(tmp_path).verify(PUBLIC,b'x'*(1024*1024+1),SIGNATURE)


def store(tmp_path,**changes):
    key=dict(key_id='key-1',producer_id='fixture-grid',public_key_b64=base64.b64encode(PUBLIC).decode(),valid_from_ns=10,valid_until_ns=100,revoked=False)
    key.update(changes)
    path=tmp_path/'trust.json';data=canonical_bytes(dict(version=1,keys=[key]));path.write_bytes(data)
    from strattester.research.financial_signatures import load_trust_store
    return load_trust_store(path,sha256(data).hexdigest())


def test_trust_key_scope_and_time_are_independently_pinned(tmp_path):
    trust=store(tmp_path)
    assert trust.key('fixture-grid','key-1',50)==PUBLIC
    for producer,key,time in [('attacker','key-1',50),('fixture-grid','other',50),('fixture-grid','key-1',9),('fixture-grid','key-1',101)]:
        with pytest.raises(ValueError):trust.key(producer,key,time)

@pytest.mark.parametrize('change',[{'revoked':True},{'valid_from_ns':True},{'valid_until_ns':0},{'public_key_b64':'bad'}])
def test_revoked_or_invalid_trust_entries_never_authorize(tmp_path,change):
    with pytest.raises(ValueError):store(tmp_path,**change).key('fixture-grid','key-1',50)
