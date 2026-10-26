"""Independent Ed25519 verification through an operator-pinned OpenSSL3 binary.

No artifact-selected command, callback, provider, public key or trust root.
OpenSSL supports bounded one-shot Ed25519; RFC8032 vectors verify this boundary.
Deployment must independently protect the executable/libraries and scratch ACLs.
"""
from dataclasses import dataclass
import base64
import binascii
import os
from pathlib import Path
import subprocess
import tempfile
from .financial_contract import integer
from .financial_snapshot import verified_bytes, bounded_json


def decode64(value,size):
    if type(value) is not str or len(value)>4*((size+2)//3):raise ValueError('invalid base64 size')
    try:result=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error) as exc:raise ValueError('invalid base64') from exc
    if len(result)!=size:raise ValueError('invalid decoded key/signature size')
    return result


@dataclass(frozen=True)
class OpenSSLVerifier:
    executable: Path
    executable_sha256: str
    scratch_root: Path

    def verify(self,public_key,message,signature):
        if (type(public_key) is not bytes or len(public_key)!=32 or type(signature) is not bytes or len(signature)!=64
            or type(message) is not bytes or not 1<=len(message)<=1024*1024):
            raise ValueError('signature input budget/type')
        executable=Path(self.executable)
        if not executable.is_absolute():raise ValueError('absolute pinned verifier required')
        verified_bytes(executable,self.executable_sha256,64*1024*1024)
        scratch=Path(self.scratch_root)
        if not scratch.is_dir() or scratch.is_symlink():raise ValueError('existing trusted verifier scratch required')
        with tempfile.TemporaryDirectory(prefix='ed25519-',dir=scratch) as directory:
            root=Path(directory)
            # RFC8410 SubjectPublicKeyInfo: fixed Ed25519 OID, never a PEM URI.
            (root/'key.der').write_bytes(bytes.fromhex('302a300506032b6570032100')+public_key)
            (root/'message').write_bytes(message);(root/'signature').write_bytes(signature)
            (root/'openssl.cnf').write_bytes(b'')
            # Do not inherit provider/engine/preload configuration from artifacts
            # or ambient OPENSSL_CONF/OPENSSL_MODULES/LD_PRELOAD variables.
            env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR') if k in os.environ}
            env['OPENSSL_CONF']=str(root/'openssl.cnf')
            try:
                result=subprocess.run([str(executable),'pkeyutl','-verify','-pubin','-keyform','DER',
                    '-inkey',str(root/'key.der'),'-rawin','-in',str(root/'message'),'-sigfile',str(root/'signature')],
                    cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    timeout=5,check=False,shell=False)
            except (OSError,subprocess.TimeoutExpired) as exc:raise ValueError('signature verifier unavailable/timeout') from exc
            if result.returncode!=0:raise ValueError('untrusted Ed25519 signature')
        return True


@dataclass(frozen=True)
class TrustKey:
    key_id: str
    producer_id: str
    public: bytes
    valid_from_ns: int
    valid_until_ns: int
    revoked: bool


@dataclass(frozen=True)
class ProducerTrustStore:
    sha256: str
    keys: tuple[TrustKey,...]

    def key(self,producer_id,key_id,at_ns):
        integer(at_ns,'signature cutoff')
        matches=[k for k in self.keys if k.key_id==key_id and k.producer_id==producer_id]
        if len(matches)!=1:raise ValueError('unknown producer/key scope')
        key=matches[0]
        if key.revoked or not key.valid_from_ns<=at_ns<=key.valid_until_ns:raise ValueError('revoked/expired producer key')
        return key.public


def load_trust_store(path,expected_sha256):
    payload=bounded_json(verified_bytes(path,expected_sha256,64*1024))
    if (set(payload)!={'version','keys'} or type(payload['version']) is not int or payload['version']!=1
        or type(payload['keys']) is not list or not 1<=len(payload['keys'])<=64):raise ValueError('trust store schema/budget')
    keys=[];seen=set()
    for row in payload['keys']:
        if type(row) is not dict or set(row)!={'key_id','producer_id','public_key_b64','valid_from_ns','valid_until_ns','revoked'}:
            raise ValueError('trust key schema')
        for name in ('key_id','producer_id'):
            if type(row[name]) is not str or not 1<=len(row[name])<=128:raise ValueError('trust key identity')
        integer(row['valid_from_ns'],'key valid_from');integer(row['valid_until_ns'],'key valid_until')
        if row['valid_until_ns']<row['valid_from_ns'] or type(row['revoked']) is not bool:raise ValueError('trust key validity')
        identity=(row['producer_id'],row['key_id'])
        if identity in seen:raise ValueError('duplicate trust key')
        seen.add(identity)
        keys.append(TrustKey(row['key_id'],row['producer_id'],decode64(row['public_key_b64'],32),
                             row['valid_from_ns'],row['valid_until_ns'],row['revoked']))
    return ProducerTrustStore(expected_sha256,tuple(keys))
