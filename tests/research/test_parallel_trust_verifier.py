"""Adversarial software-only G0 verifier boundary checks."""
import base64
import json
from pathlib import Path
import runpy

import pytest

from strattester.research.financial_snapshot import canonical_bytes
from strattester.research.financial_signatures import OpenSSLVerifier


def fixture(root):
    return runpy.run_path(str(Path(__file__).with_name('test_g0_signed_receipt.py')))['fixture'](root)


class AlwaysAttests:
    def verify(self, *args):
        return True


class SubstitutedVerifier(OpenSSLVerifier):
    def verify(self, *args):
        return True


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
    with pytest.raises(ValueError, match='independent pinned verifier required'):
        verify(verifier=verifier)
