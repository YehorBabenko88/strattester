# Independent Python/Git trust review

Base: d27ad12ea32e4e8fa2cabed0952a516dbcbc6418. No production source change or confirmed correctness defect. New tests exercise provisioning/rotation and failure rejection independently. Consequently there is no defect RED/GREEN claim. The initial environment-error log records a pytest default temporary-directory permission failure; the successful run uses a task-owned temporary root.

| Boundary | Required policy / observed behavior |
| --- | --- |
| Trust provisioning | External SHA256 pin must match exact JSON bytes; changing the file requires independent repinning. |
| Rotation | New key ID can overlap validity; duplicate producer/key IDs are rejected even with disjoint validity. |
| Revocation | Revoked entry rejects all timestamps; active consumers must replace already loaded immutable trust-store instances. File replacement cannot retroactively revoke an in-memory instance. |
| Scope/time | Producer and key IDs must match together; validity endpoints are inclusive. |
| Verifier identity | Wrong executable byte pin rejects before subprocess invocation. |
| Verifier failure | Timeout or launch error rejects and removes temporary verification files. |
| Owner helper | Existing tests cover canonical bytes, input/package binding, expiry, integer limits and exact operation. This helper does not authorize G1. |
| Git provenance | Existing pure Git tests exercise committed object bytes, skip-worktree, excluded extra files and replacement blobs using owned temporary repositories. Only Python source_snapshot helper was reviewed; no native sandbox source or execution. |

Verification: `..\financial-venv\Scripts\python.exe -m pytest tests/research/test_trust_rotation_review.py tests/research/test_financial_signatures.py tests/research/test_owner_intent_v2.py tests/native/test_native_source_identity.py --basetemp=..\trust-review-pytest-owned-20261026 -q` => 48 passed. Real OpenSSL RFC8032 vector tests ran; new launch-failure tests use an inert owned file and mocked subprocess.

Limits: measuring an executable and subsequently launching its path leaves an unqualified measurement-to-path-launch race. Hashing does not qualify dependent libraries, installation protection, scratch protection or concurrent namespace replacement. No native implementation was attempted. No physical machine, service, production database, G1 or trading operation was performed; no CI/packager manifest changed.
