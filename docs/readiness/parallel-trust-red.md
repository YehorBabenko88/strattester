FF                                                                       [100%]
================================== FAILURES ===================================
______ test_untrusted_verifier_cannot_attest_forged_signatures[callback] ______

tmp_path = WindowsPath('C:/Users/LS-5/Documents/Codex/2026-10-24/files-pasted-by-the-user-codex/work/trust-red-20261027/test_untrusted_verifier_cannot0')
kind = 'callback'

    @pytest.mark.parametrize('kind', ['callback', 'subclass'])
    def test_untrusted_verifier_cannot_attest_forged_signatures(tmp_path, kind):
        *_, verify = fixture(tmp_path)
        path = tmp_path / 'receipt.json'
        receipt = json.loads(path.read_text())
        receipt['signatures'] = {role: base64.b64encode(bytes(64)).decode()
                                 for role in ('owner', 'provider')}
        path.write_bytes(canonical_bytes(receipt))
        verifier = (AlwaysAttests() if kind == 'callback' else
                    SubstitutedVerifier(tmp_path/'not-an-executable', '0'*64, tmp_path))
>       with pytest.raises(ValueError, match='independent pinned verifier required'):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests\research\test_parallel_trust_verifier.py:37: Failed
______ test_untrusted_verifier_cannot_attest_forged_signatures[subclass] ______

tmp_path = WindowsPath('C:/Users/LS-5/Documents/Codex/2026-10-24/files-pasted-by-the-user-codex/work/trust-red-20261027/test_untrusted_verifier_cannot1')
kind = 'subclass'

    @pytest.mark.parametrize('kind', ['callback', 'subclass'])
    def test_untrusted_verifier_cannot_attest_forged_signatures(tmp_path, kind):
        *_, verify = fixture(tmp_path)
        path = tmp_path / 'receipt.json'
        receipt = json.loads(path.read_text())
        receipt['signatures'] = {role: base64.b64encode(bytes(64)).decode()
                                 for role in ('owner', 'provider')}
        path.write_bytes(canonical_bytes(receipt))
        verifier = (AlwaysAttests() if kind == 'callback' else
                    SubstitutedVerifier(tmp_path/'not-an-executable', '0'*64, tmp_path))
>       with pytest.raises(ValueError, match='independent pinned verifier required'):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests\research\test_parallel_trust_verifier.py:37: Failed
=========================== short test summary info ===========================
FAILED tests/research/test_parallel_trust_verifier.py::test_untrusted_verifier_cannot_attest_forged_signatures[callback]
FAILED tests/research/test_parallel_trust_verifier.py::test_untrusted_verifier_cannot_attest_forged_signatures[subclass]
2 failed in 1.31s
