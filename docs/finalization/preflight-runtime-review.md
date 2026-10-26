# Preflight implementation and independent review

Base `d27ad12ea32e4e8fa2cabed0952a516dbcbc6418` and related Draft PRs15–41
were rechecked; four existing comments remain unchanged. Native source is
unchanged. The stopped native implementation/review is not retried or bypassed.

## Confirmed software changes

1. Two deterministic CPU RED cases reproduced overlapping training RNG windows
   and experiment reseeding of the caller. A shared reentrant CPU slot now
   coordinates participating constructors, fits and checkpoint reconstruction.
   Waiting is bounded to30 seconds with cancellation polling at most50ms.
   CPU RNG plus deterministic enabled/warn-only policy restore on exceptions;
   seeded constructors do not seed CUDA. Legacy unseeded constructors retain
   their documented RNG consumption. Parallel weights/losses are compared with
   sequential runs; actual checkpoint reconstruction waits for active fits.
   Arbitrary external Torch calls and other processes do not share this lock;
   callers must cooperate or isolate processes. This is not OS/GPU isolation.
2. Decimal funding rates lost residuals before float summation. Exact80-digit
   isolated Decimal accumulation now precedes final float reporting. Rates have
   explicit bounded scale and existing bps/coverage/exposure semantics remain.
   No authenticated funding producer schema/input exists; no real events or
   key authority were invented. Price/cost arithmetic remains legacy float.
3. Sealed Grid receipt float watermarks/timeframes compared equal to pinned
   integers and were reconstructed as integers. Canonical receipt comparison
   now rejects this type substitution. Actual raw Grid DDL/migrations at
   `d537d525296ef34f727996e240ae6c60102c6082` match fixture hashes; the remote
   Grid main SHA was rechecked. This does not attest deployed stores or invent
   retained revisions, first availability or producer-issued epochs.
4. Explicit verify-executables inventories pinned bytes without execution.
   Independent review reproduced mixed-separator UNC and reserved device
   aliases reaching target IO; lexical admission rejects these before IO.
   Inventory is not loaded-image identity, publisher/dependency attestation,
   native confinement, or a solution to the separate verifier path-launch race.

## Independent reviews and evidence limits

The separate Python trust review executed48 cases, with no production defect
claim; rotation/revocation, duplicate scope, executable pin and launch failure
tests are selectively imported. Initial temp-permission errors are preserved
outside source, not disguised as defect REDs. See trust-policy-review-next.md.
The same reviewer independently inspected CPU changes and ran22 CPU cases;
no actionable issue was found. Inventory review found the two path families
above; root saved5 reproduced failures followed by18 passes, all on inert owned
files with target IO intercepted. No network/native execution was performed.

All source stdout logs are retained externally with the final delivery. Source
results do not qualify a new HEAD: final node manifest and hosted CI must run
on the committed candidate. Per-file source/tree/blob/reason/contracts are in
preflight-import-provenance.json. Raw failed/skipped/deselected counts remain
separate from successful required gates.

## Remaining native guarantee matrix (read-only source review)

| Boundary | Present component | Missing mandatory guarantee |
|---|---|---|
| Owner v2 | Bounded canonical signature, package/input/source/binary/VM/limit/expiry binding | Provisioned current role/identity registry, revocation policy and admitted owner-to-worker bridge |
| Nonce | Persistent relative NTFS claim, flush/tombstone, replay refusal | Actual launch coupling, VM rollback and hostile-admin/power-loss proof |
| Executables | Pinned file bytes; independent read-only inventory | Loaded image/dependency closure and atomic measurement-to-execution binding |
| Handles/filesystem | Retained input and owned-probe handle components | Actual interpreter/dependency/output namespace confinement and lifetime races |
| Suspended admission | Owned probe joins queried Job Object before resume | All actual research constraints independently verified before resume |
| Egress | Owned direct TCP WFP experiment | DNS services/proxies, UDP, all IPv4/IPv6, loopback, descendants and network-capable handles |
| Resources | Queried Job Object component; software memory/batch/output admission | Actual research CPU/RAM/wall/process/output enforcement and OOM/cancellation/crash containment |
| Recovery/cleanup | Software interruption/replay and component cleanup receipts | Full worker cleanup, physical power-loss/VM rollback durability and independent QA |
| Default behavior | --launch/test-disposable fail closed | No physical GO may be inferred from any component receipt |

External Grid truth, authenticated funding, real OOS, actual GPU/full upstream
equivalence, target G0 evidence, independent native qualification and exact owner
G1 authorization remain BLOCKED. G1 is NOT_AUTHORIZED and trading is NO-GO.
