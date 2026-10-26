# Independent continuation source review

Integration base: `c09592be649d249c6b082a5e21cbeea2800a0049`.
The PR21 HEAD and all four current comments were read before work; no new owner
authorization or architecture approval is inferred. All imported source blobs,
trees, reasons, contract changes and compatibility notes are recorded in
`continuation-import-provenance.json`. Cherry-pick messages retain source commits.

## Accepted focused changes

* Grid `6fd2a929ff30815ff2ce12d32496f6d09dd90c4f`: validation cancellation and
  independently resealed second-store negative receipts. Source selection58
  passed/40 deselected; excluded PostgreSQL/signer execution is not claimed.
* Recovery `a40c23c7a67d9188d4861e6ac43118fa42152a61`: publication identity
  excludes its own receipt. Source checkpoint/session/offline suite30 passed;
  experiment/walk-forward suites33 passed. Actual crash/concurrency/replay tests
  remain software tests in owned temporary directories.
* Checkpoint `925d991ff78d1142830b7fea2781cfa552ba8c42`: preserve caller CPU
  RNG during reconstruction, successful and rejected load. Source suite32 passed.
  This is not concurrent-thread RNG isolation or power-loss durability.
* Funding `f4fb6509cde00f5f031fee115475a29b134ea1f0`: optional fixed-entry-
  notional signed settlement bps, Decimal oracles and explicit unauthenticated
  coverage. Source broader suite100 passed/3 passed subtests. Root additionally
  enforces aggregate10k events, includes the module in isolated packages and
  uses `math.fsum` for Python3.11 cash cancellation correctness.
* Dataset guard `1cfa5a73530bb83bc4685fe30aa162b14fdf4195`: three minimum-
  valid-history cases against the actual implementation; no PR37 code imported.

These source results are provenance only. New common-HEAD CI and raw test counts
are required; no result is inherited as a later-HEAD PASS.

## Independent review of root trust/provenance changes

A separate reviewer executed the exact f3dfee4 crypto gate and two genuine
signature tests, including renamed producer/key identities:2 passed. It also
executed the extracted portable source-snapshot function and owned-temp Git
tests:4 passed. No native Windows implementation was executed or modified.
The known-public-key gate covers the distributed fixture key, not arbitrary
private-key compromise. Pinned trust files still need independent provisioning,
rotation and revocation outside artifact control.

## Supported-version RED evidence

The new funding cancellation oracle is GREEN under Python3.12. The same test
failed on actual hosted Python3.11, job121757439307/run40375529810 at
`f3dfee421cdadce39df1c3aba107f623ceeb0b55`: obtained0 instead of expected
`-1e-16`. Windows3.11 also failed, while3.13 jobs passed. This is a real
supported-version failure, not an emulated GPU/native result. Raw failed logs
are retained externally; final CI must independently verify the fsum correction.

## Rejected / unimported independent source changes

PR35 `213ec644abdea95945f6ade9917090ac7630221a` has incompatible standalone
funding/registry definitions. Its oracle accepts a negative timestamp rejected
by the real ledger; calibration can return infinite squared standardized error
for finite input. These were reproduced against source modules and are not
defects of this integration. Source blobs:
`system_audit_oracles.py=e02fbd4a8d2e2856df693a8a3cc9035b58167346`,
`system_audit_calibration.py=42310010bc8e6635fccaa80d7ec61462e78e7b51`.
Do not import these helpers as trusted acceptance or producer contracts.

PR37 `5541afa3e37781642406fb7774d2fbc09ac6fc1d` changes an already-correct
sample boundary into an out-of-range target index. Exact source tests yielded
13 passed/3 IndexErrors, versus16 passed on the integrated implementation.
Its standalone resampling oracle's3 passing tests do not prove product
resampling behavior. See `../research/pr37-sample-boundary-review.md` for exact
blobs and the additional minimum-history regression.

PR38 `253454acc10ce1f7abd244931630c1632c687ae3` was read only as an offline
metadata/ZIP/STOP helper reference. Its functions always remain BLOCKED and do
not independently validate native process isolation or owner authorization.
They were not wired into acceptance as a substitute for actual evidence.
Experimental PR36 remains unimported; stopped native work is not retried.

## Remaining blockers

See `independent-continuation-native-matrix.md` for exact missing native
guarantees and refusal/independent acceptance conditions. Native Grid historical
truth and producer epochs, authenticated funding, real OOS, GPU, physical target
G0 and owner G1 authorization remain absent. Concurrent threaded RNG users must
be serialized or isolated in separate processes. Resource admission bounds are
software estimates, not enforcement of process RSS or full sandbox limits.

`PHYSICAL_G1=NOT_AUTHORIZED`; `TRADING=NO-GO`; production/main/service mutation
is forbidden. No active LS5/PC4 operations or G1 were performed.
