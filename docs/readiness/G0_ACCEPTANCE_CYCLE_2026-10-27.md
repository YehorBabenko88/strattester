# G0 acceptance cycle — 2026-10-27

Baseline PR21 `9c913494481abbfc997e1c0a9dd46fab04576ebb`, tree
`a9201b51bfe76abfa3d0a3fe9fa4f9d2ea230535`. Final source/tree and CI receipts
are published separately after committing; earlier PASS never certifies them.

## Read-only G0 preparation

Confirmed P2: Windows PowerShell5.1 cannot call SHA256.HashData/ToHexString.
The collector now uses disposable SHA256.Create/ComputeHash and BitConverter.
Three actual mocked PowerShell contracts failed before correction and passed
after it. Every host inventory command was replaced by fixture functions;
neither LS5/PC4 nor another real target was inventoried. A separate reviewer ran
the three cases and nine dataset tests:12 passed, zero skipped.

UDP endpoint ownership and GPU driver observations are now included. Optional
TCP/UDP/GPU queries distinguish UNAVAILABLE from an observed list (including an
empty list). Exceptions are not serialized, preventing provider/private-path
disclosure. Core identity/OS/ACL failures still abort; they are not fabricated.
The report always says BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE. Driver names
are not CUDA compatibility; UUID hashing is not independent VM attestation.
Process names/PIDs do not identify database ownership, and a root ACL summary
does not prove ancestor namespace protection. Dependency/loaded-image evidence
must be collected separately with pinned tools on the future approved VM.

## Grid producer facts and OOS prerequisites

Remote Grid HEAD/main rechecked at `d537d525296ef34f727996e240ae6c60102c6082`;
math HEAD/main at `ccfe97dd88b1ebee9bd19795002a30d0bd1c1ca3`.
The existing actual-DDL catalog adapter and sealed export contract are tested on
owned fixtures, never production connections. Latest-state rows, migration
claims, source hashes, independent database transactions or a signed epoch label
do not establish retained revisions, first knowledge, or a coherent producer cut.
No historical facts were backfilled. Native historical export remains BLOCKED.

Before real OOS, independently admit retained first-availability/revision facts,
full venue/market/symbol/timeframe identities, source and schema/build pins,
cross-store producer cut, coverage/quality receipts, authenticated funding and
fees/fills/slippage definitions. Freeze universe/folds/holdout/embargo/seeds,
hyperparameters/controls/criteria before evaluating. Train-only transforms and
fresh per-fold models, disjoint labels, dependence-aware intervals, calibration,
terminal liquidation and independent checkpoint/ledger replay remain mandatory.
Never substitute synthetic profitability or zero missing costs for real evidence.

## Independent source disposition

PR37 corrected its dataset loop to the existing integration implementation.
Its revised last-target expectation `times[-2]` remains wrong: last legal origin
is n-horizon-1 and target is n-1. New commit1ba067f repeats that inconsistency.
No dataset or revised assertions are imported. Original independent source
tests were run in memory against the baseline; three conflicting cases fail.
This is an import rejection, not a new integration defect.

PR35's HMAC helper has unbounded iterator materialization, float rates and
implicit market identity. HMAC bytes cannot independently establish a producer
role/history. Do not merge it into the signed Decimal runner. A separate bounded,
externally pinned Ed25519 intake may verify bytes, with historical truth and
runtime funding admission explicitly unqualified. Signed assertions alone do
not clear Grid, funding completeness or real OOS prerequisites.

PR42/43 introduce a separate read-only results/provenance API based on main.
They require compatibility and independent source/receipt review before any
future import; the PR21 research runtime does not blindly merge those branches.
Earlier selectively imported PR15–28/40–41 provenance remains historical source
evidence. No source branch is overwritten.

## Owner-signable disposable G1 plan

The complete operational constraints in
`docs/finalization/preflight-g0-owner-plan.md` remain mandatory. The final
delivery includes an UNSIGNED owner-v2 template outside its hashed package.
No real owner key, fresh nonce, issue/expiry time or target identity is invented.
Fill every field from independently verified facts, then sign canonical owner-v2
bytes under domain STRATTESTER_PHYSICAL_G1_OWNER_V2 plus NUL. An invalid or
incomplete template must fail before admission.

Required bindings: final exact source/tree; hosted binary SHA256 plus separate
actual loaded-executable/dependency verification; final ZIP hash also under
input_hashes.package; signed snapshot/checkpoint, funding policy/manifest if used,
producer/owner trust policies and executable inventory hashes; independent VM
identity; fresh durable nonce; issue/expiry window at most600 seconds; sole
operation synthetic_cpu_inference. Maximum ceilings:CPU10%, RAM2147483648 bytes,
wall60 seconds, output67108864 bytes, max_processes1. These are requested limits,
not proof of their enforcement. Do not sign a training/backtest/GPU operation
under the inference-only owner schema.

| Boundary | Future allowed operation | Required STOP evidence |
|---|---|---|
| VM | Exact disposable identity; no production/shared mounts | Any identity/mount/ownership uncertainty |
| Network | None: DNS/UDP/TCP/IPv4/IPv6/loopback/proxy/descendants denied | Missing independent full-network negative controls |
| Input | Read pinned immutable artifacts only | Changed hash/role/schema/epoch or mutable namespace |
| Process | One exact approved worker after all pre-resume controls | Missing signed-intent bridge, loaded-image, token/job/handle/resource proof |
| DB | No connections or mutations | Any DB/client/credential exposure |
| Output | Exact owned staging/output paths, bounded logs and receipts | Overflow, partial publication, cancellation or cleanup uncertainty |

STOP before execution until independent QA qualifies every native guarantee and
owner separately authorizes the exact plan. Existing component receipts and
Python mocks do not establish filesystem/namespace confinement, deny-all egress,
descendant/output/resource bounds, cancellation/crash containment or power-loss
durability. The blocked native implementation/review is not resumed.

Cleanup manifest must enumerate exact disposable paths, object identities,
hashes, permitted files and any exact approved process identity. Preserve logs,
partial outputs, durable nonce tombstones and errors. Do not recursively delete
unknown paths, follow reparses, clear nonce history or control active services.
Interrupted publication is not completion; recovery starts from pinned inputs
under a newly qualified authorization, never reused consumed nonce. Rollback
means discard only independently reviewed disposable outputs, not production
restoration. No cleanup is executed on active LS5/PC4 by this plan.

## Readiness

No new confirmed P0. P1 external blockers: native producer history/coherence,
trusted deployment/role provisioning, actual multi-market OOS, GPU/full upstream
equivalence, target G0, complete native isolation and independent QA/owner G1.
P2 corrected G0 PowerShell compatibility; remaining physical durability,
loaded-image binding and real cashflow/fill definitions are unqualified.

`PHYSICAL_G0_READINESS=PLAN_READY_TARGET_EVIDENCE_BLOCKED`;
`PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION=NO_GO`;
`G1=NOT_AUTHORIZED`; `TRADING=NO-GO`; `MAIN_MERGE=FORBIDDEN`;
`PRODUCTION_DB_MUTATIONS=FORBIDDEN`.
