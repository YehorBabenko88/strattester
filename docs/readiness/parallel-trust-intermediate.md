...........................................F...........................  [100%]
================================== FAILURES ===================================
_________ test_only_three_pinned_inputs_read_no_referenced_artifacts __________

tmp_path = WindowsPath('C:/Users/LS-5/Documents/Codex/2026-10-24/files-pasted-by-the-user-codex/work/trust-green-20261027/test_only_three_pinned_inputs_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001CCA3C0EDE0>

    def test_only_three_pinned_inputs_read_no_referenced_artifacts(tmp_path, monkeypatch):
        import socket
        import sqlite3
        from strattester.research import financial_g0_receipt as module, financial_signatures as signatures
        *_,verify=fixture(tmp_path)
        real=module.verified_bytes;calls=[]
        def read(path,*args):
            calls.append(Path(path).name)
            return real(path,*args)
        def forbidden(*args,**kwargs): raise AssertionError('unexpected external operation')
        monkeypatch.setattr(signatures.OpenSSLVerifier, 'verify', lambda self, *args: True)
        monkeypatch.setattr(module,'verified_bytes',read)
        monkeypatch.setattr(signatures,'verified_bytes',read)
        monkeypatch.setattr(subprocess,'Popen',forbidden)
        monkeypatch.setattr(socket,'socket',forbidden)
        monkeypatch.setattr(sqlite3,'connect',forbidden)
        assert verify()['status']=='BLOCKED'
>       assert calls==['policy.json','receipt.json','trust.json']
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\research\test_g0_signed_receipt.py:199: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
tests\research\test_g0_signed_receipt.py:49: in verify
    return verify_g0_receipt(**{**args,'verifier':roles[0][1],'now_ns':150,**changes})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

manifest_path = 'C:\\Users\\LS-5\\Documents\\Codex\\2026-10-24\\files-pasted-by-the-user-codex\\work\\trust-green-20261027\\test_only_three_pinned_inputs_0\\receipt.json'
manifest_sha256 = '734aca6a1fd3d74c6d3b7710bf22724d4117ac4c09e7459e2038ef27b134d815'
policy_path = 'C:\\Users\\LS-5\\Documents\\Codex\\2026-10-24\\files-pasted-by-the-user-codex\\work\\trust-green-20261027\\test_only_three_pinned_inputs_0\\policy.json'
policy_sha256 = 'e4962a6bd99b16fdf8cf3653de1db32bd31b8017aa94dfeab8d14bdfda5b8831'
trust_store_path = 'C:\\Users\\LS-5\\Documents\\Codex\\2026-10-24\\files-pasted-by-the-user-codex\\work\\trust-green-20261027\\test_only_three_pinned_inputs_0\\trust.json'
trust_store_sha256 = 'bbec929961f709f15a72e1e254bf7a2c19b2f9fd57edf892baf3edd7840d837d'
verifier = <tests.research.test_g0_signed_receipt.test_only_three_pinned_inputs_read_no_referenced_artifacts.<locals>.SignatureStub object at 0x000001CCA21CB590>
now_ns = 150

    def verify_g0_receipt(*, manifest_path, manifest_sha256, policy_path, policy_sha256,
                          trust_store_path, trust_store_sha256, verifier, now_ns):
        # Callbacks/subclasses can attest forged bytes without checking Ed25519.
        if type(verifier) is not OpenSSLVerifier:
>           raise ValueError('independent pinned verifier required')
E           ValueError: independent pinned verifier required

strattester\research\financial_g0_receipt.py:29: ValueError
=========================== short test summary info ===========================
FAILED tests/research/test_g0_signed_receipt.py::test_only_three_pinned_inputs_read_no_referenced_artifacts
1 failed, 70 passed in 26.28s
