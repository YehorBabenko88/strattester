# Independent bounded artifact security probes

Target: `67301726d250973602b964adabdb9eb8d50d0f13`, Windows, existing Python 3.12 CPU venv. No tracked files changed, installations, production DB access, services or G1 operations. Fixtures created and removed under `work/security-independent-*` only.

Reproduce from task root:

```powershell
.\work\financial-venv\Scripts\python.exe .\work\security_independent_probe.py
```

Raw executed results: `work/security-independent-results.json`. Probe uses bounded monkeypatches to schedule a concurrent staging-file mutation or abrupt child-process exit at the actual `os.link` publication boundary. These are deterministic fault-injection reproductions; no assertion that an unprivileged remote attacker already has filesystem access.

## P1: publication succeeds with digest not matching published bytes under concurrent staging modification

`strattester/research/financial_checkpoint.py:46–55` closes the writable named staging file before publishing it by pathname with `os.link`. A writer with directory/file access can change the staging bytes after close and before publication. The API returns SHA256 of the original memory buffer, without checking the published bytes. Executed probe changed the staged file to 33 bytes, publication returned successfully, and returned SHA256 differed from actual final file SHA256.

**Boundary and consequence:** this is an integrity/availability publication defect under shared-writable artifact-directory threat. It is not an executable-deserialization or trusted-hash bypass: `load_checkpoint(final, returned_sha)` rejected with `ValueError`. A private, enforced ACL sandbox can exclude the assumed adversary, but current API does not establish that precondition or accept a trusted root. Owner authorization of a sandbox path alone does not establish its ACL or absence of reparse ancestors.

**Suggested closure:** establish verified private artifact directories with trusted-root confinement and stable directory/handle identity; retain suitable exclusive file identity through publication; verify published descriptor bytes against intended digest and reject/remove only owned artifacts on mismatch. Windows needs actual handle/reparse and sharing semantics. Add fault-injection test asserting no successful publication with mismatched digest. Do not claim a complete same-user adversary defense using only pre/post pathname checks.

## P1/G1 blocker: abrupt publication recovery is not established

Actual subprocess `os._exit(77)` immediately before `os.link`: no final artifact, one orphan `.checkpoint-*` file. Immediately after successful `os.link`: complete final pathname and one orphan `.checkpoint-*` hardlink remain, with no returned digest/registered result. This matches comments at lines 49–50 for pre-publication crash, but restart cleanup/ownership/journal, disk accumulation bounds, reconciliation and parent-directory fsync durability are not implemented/proven here. Python `finally` only covers handled exceptions, not process death/power loss.

**Positive executed control:** handled `KeyboardInterrupt` before link leaves no final or temp. Existing exclusive `os.link` prevents overwrite. Neither abrupt crash was misclassified as a successfully registered checkpoint by this probe.

Do not blindly delete unknown `.checkpoint-*` files from shared directories. Cleanup needs a job-owned directory or authenticated manifest and safe descriptor identity checks. No cleanup of real files was attempted.

## P2: hardlink policy absent

`financial_snapshot.py:27–38`: a regular NTFS artifact with `st_nlink == 2` was accepted by `verified_bytes`. Digest matched the bytes read from its opened handle. This demonstrates absence of hardlink rejection/trusted-root policy, **not** a hash binding bypass. Concurrent alias writes still cannot make different bytes satisfy a trusted SHA256 absent collision; consumers must exclusively use verified bytes rather than reopen a pathname. A requested strict single-link policy requires explicit enforcement and Linux/Windows tests. The publication scheme itself temporarily creates two links; any new rejection must account for publication cleanup/crash recovery.

## P2: malformed JSON exception contract incomplete

A correctly hash-bound 2,401-byte nested-array snapshot raises `TypeError` at `financial_snapshot.py:49` because the root is not a mapping. File-size bounds do not enforce structural JSON depth/node limits. This is fail-closed for this caller; no false PASS, deserialization execution or OOM was observed. It can bypass callers that catch only the documented `ValueError` class. Reject root type before `set(payload)`, bound JSON structural complexity, normalize JSON/recursion/schema errors. Do not claim JSON bomb/OOM exploitation from this bounded probe.

## Windows confinement status and external source

No junction/symlink privilege or ACL was changed to produce a test. Windows `O_NOFOLLOW` is absent; the API's pre-open `Path.is_symlink()/is_file()` at lines 30–31 does not atomically reject swapped symlinks, ancestor junctions or all reparse tags. A successful native exploit is **not** claimed. Handle-based Windows confinement, Linux FIFO/path-swap races, real process-level concurrent job admission and power-loss durability remain unverified.

Inspected `origin/parallel/alphafold-qa-security` at `2c5e378` (full SHA available via git). That branch contains `docs/security/pr21-independent-physical-g1-assessment-20261024.md`; its snapshot implementation is an older tree without `financial_snapshot.py`. Its P0 acceptance finding is being handled independently by the integration lead; this report does not duplicate or certify that fix.

## Verdict

Security subsystem is **not a G1 authorization primitive**. Above executed probes are targeted evidence, not a complete system audit. Production filesystem confinement, resource/process ceilings, sandbox ownership and crash recovery remain G1 blockers until independently verified. GPU, live Grid, PostgreSQL and physical nodes were not exercised.
