# Trust verifier contract audit, 2026-10-27

Baseline: f60869686a51693799b4844a1af49c9b39ba45d5. Software/disposable paths only.

G0 previously accepted any caller-supplied verifier returning literal True, including callbacks and OpenSSLVerifier subclasses overriding verify. Two tests replace both signatures with zero bytes and reproduce this acceptance. G0 now requires the exact OpenSSLVerifier type, consistent with owner authorization. This is API-contract tightening (P2), not a sandbox against malicious Python callers, class monkeypatching, or runtime compromise. No P0/P1 admission defect claimed: the old result was always BLOCKED.

External manifest/policy/trust SHA256 pins, exact schemas, independent role identities and distinct public keys, issue/current key validity and revocation, bounded policy/receipt expiry, signature domain separation, candidate source/tree/package, rollback and delivery hashes remain checked. Their truth is not established merely by signatures. Existing nonce is syntax-checked only. No durable nonce journal or consumption transaction is introduced; repeated signature-only verification is deliberately permitted and reports replay protection NOT_IMPLEMENTED_NO_ADMISSION. Physical G0, G1, deployment and trading remain blocked. No native service, target or database was accessed.

The sole baseline test adaptation (authorized by parent) patches the exact trusted class method inside its isolated read-boundary test; it preserves policy/receipt/trust read order and forbidden subprocess/socket/SQLite assertions. New adversarial tests do not monkeypatch the production verifier.

RED: 2 expected failures (forged signatures accepted), 1.31s. Intermediate: 70 passed, 1 failure in old SignatureStub test, 26.28s; retained unchanged log. That run imported the old test before the test edit, so pytest's displayed source lines may reflect the later on-disk file. Final: 99 passed, 0 failed/skipped/deselected, 22.83s, five targeted trust files. Full suite and hosted CI were not awaited. OMP_NUM_THREADS=1, MKL_NUM_THREADS=1; existing financial-venv, no installs; explicit fresh trust-red/green/final-20261027 basetemp paths under work. Tests: test_parallel_trust_verifier.py, test_g0_signed_receipt.py, test_financial_owner_authorization.py, test_financial_signatures.py, test_owner_intent_v2.py.

Source baseline blobs: financial_g0_receipt.py eb8eb5f8f35308a3bc5656ad4773894503494512; test_g0_signed_receipt.py 3475a7295b341de0adc50dc9499d3ad5719e7dc0. Exact final commit/tree/blobs are reported separately to avoid self-referential provenance.
