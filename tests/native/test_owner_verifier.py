"""Native signature verification is read-only; no research process admission."""
import os,json,subprocess,unittest,tempfile,time,hashlib
from pathlib import Path

@unittest.skipUnless(os.name=='nt' and os.environ.get('NATIVE_BROKER'),'compiled Windows broker required')
class NativeOwnerTests(unittest.TestCase):
    def signed(self,folder,change=None):
        exe='C:/Program Files/Git/usr/bin/openssl.exe'
        def ssl(*a):return subprocess.run([exe,*a],capture_output=True,check=True).stdout
        ssl('genpkey','-algorithm','ED25519','-outform','DER','-out',str(folder/'key.der'))
        pub=ssl('pkey','-inform','DER','-in',str(folder/'key.der'),'-pubout','-outform','DER')[-32:];(folder/'pub').write_bytes(pub)
        b=os.environ['NATIVE_BROKER'];meta=json.loads(subprocess.check_output([b,'--owner-vm-identity'],text=True))
        (folder/'input').write_bytes(b'synthetic immutable bytes')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        now=time.time_ns();p=dict(version=2,purpose='PHYSICAL_G1_AUTHORIZATION',owner_id='ephemeral-test',key_id='test',target_sha=meta['source_sha'],tree_sha=meta['tree_sha'],binary_sha256=sha(Path(b)),package_sha256='d'*64,vm_identity_sha256=meta['vm_identity_sha256'],input_hashes={'snapshot':sha(folder/'input')},issued_at_ns=now-1_000_000_000,expires_at_ns=now+60_000_000_000,nonce='a'*64,operations=['synthetic_cpu_inference'],limits=dict(cpu_percent=10,memory_bytes=67108864,wall_seconds=2,output_bytes=1024,max_processes=1))
        if change:p.update(change)
        raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();(folder/'plan').write_bytes(raw)
        (folder/'message').write_bytes(b'STRATTESTER_PHYSICAL_G1_OWNER_V2\0'+raw)
        ssl('pkeyutl','-sign','-rawin','-keyform','DER','-inkey',str(folder/'key.der'),'-in',str(folder/'message'),'-out',str(folder/'sig'))
        (folder/'paths').write_text(json.dumps({'snapshot':str(folder/'input')},sort_keys=True,separators=(',',':')))
        return [b,'--verify-owner',str(folder/'plan'),sha(folder/'plan'),str(folder/'sig'),sha(folder/'sig'),str(folder/'pub'),sha(folder/'pub'),meta['source_sha'],meta['tree_sha'],sha(Path(b)),'d'*64,meta['vm_identity_sha256'],str(folder/'paths')]

    def test_independent_openssl_signature_and_native_verifier_agree(self):
        with tempfile.TemporaryDirectory(prefix='owner-v2-') as t:
            p=subprocess.run(self.signed(Path(t)),capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            r=json.loads(p.stdout);self.assertTrue(r['signature_verified']);self.assertFalse(r['process_created']);self.assertFalse(r['nonce_consumed'])

    def test_signed_wrong_vm_inputs_expiry_and_boolean_limits_fail(self):
        for change in ({'vm_identity_sha256':'0'*64},{'input_hashes':{'snapshot':'0'*64}},{'expires_at_ns':1},{'limits':dict(cpu_percent=True,memory_bytes=67108864,wall_seconds=2,output_bytes=1024,max_processes=1)}):
            with self.subTest(change=change),tempfile.TemporaryDirectory(prefix='owner-v2-') as t:
                p=subprocess.run(self.signed(Path(t),change),capture_output=True,text=True,timeout=20)
                self.assertEqual(p.returncode,78,p.stdout);self.assertFalse(json.loads(p.stdout)['process_created'])

    def test_vm_measurement_is_read_only(self):
        p=subprocess.run([os.environ['NATIVE_BROKER'],'--owner-vm-identity'],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        r=json.loads(p.stdout)
        self.assertRegex(r['vm_identity_sha256'],'^[0-9a-f]{64}$')
        self.assertRegex(r['source_sha'],'^[0-9a-f]{40}$')
        self.assertFalse(r['process_created'])

    def test_malformed_owner_request_never_authorizes(self):
        p=subprocess.run([os.environ['NATIVE_BROKER'],'--verify-owner'],capture_output=True,text=True,timeout=15)
        r=json.loads(p.stdout)
        self.assertEqual(p.returncode,78)
        self.assertFalse(r['process_created'])
        self.assertEqual(r['physical_g1'],'NOT_AUTHORIZED')
