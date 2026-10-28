# G0 collector, funding revisions and read-only results readiness

Baseline HEAD33fd4dcf5dd1f7c16130567f0b24915931d8595d,
treee9ebd051277582f68941d79bbe20da917f9c0e45. Final source/tree, hosted job IDs
and original artifact SHA256 are published separately after commit. Previous
HEAD CI remains historical evidence and never certifies this change.

## Confirmed corrections and selective source imports

PR47 fixes G0 evidence integrity/redaction: invalid or absent GUID/hostname
produced a plausible identity hash, core provider errors could escape as raw
diagnostics, missing facts lacked explicit classification, and singleton
collections changed JSON shape. First behavioral RED16failed/5passed; additional
invalid-GUID REDs retained separately. Final41 mocked PS5.1/7 contracts passed;
independent reviewer reran41. Real providers and physical targets were not queried.
Metadata fields remain private evidence; arbitrary strings are not globally
sanitized. Missing/unavailable required facts still block target acceptance.

PR45 adds35 genuine signed funding negatives. It found no implementation defect:
unknown revision semantics, conflicting duplicate settlements/events in either
order, trust validity/rotation/revocation, artifact mutation, external byte pins
and complete partition identity already fail closed.98source tests passed.
No first/latest-revision guessing is implemented. Signature verification cannot
prove retained availability/revisions or coherent producer cuts; actual funding
integration remains NOT_ENABLED. Decimal tests retain exact cancellation and
settlement semantics; real funding/OOS remains BLOCKED.

PR46 selectively imports PR42's opt-in WSGI contract with all results disabled.
Root review found initial resolve-before-admission could reach nonlocal/linked
source paths.13 mock-only RED failures then40 source GREEN tests verified local
lexical admission before filesystem/SQLite access. Independent API selection:
39passed (source agent's40 also includes the existing runner case). No listener,
database creation/migration, result deserialization or worker activation is added.
Capabilities are explicitly false and result routes503. Ordinary CLI behavior,
financial runner, result writers, native source/build and workflows are unchanged.
Source API path correction was applied before integration publication; no claim
is made of an existing PR21 API vulnerability before the module was introduced.

PR43 producer/read admission is deferred. Its optional owned-run route needs
binding to actual financial report metrics, immutable feature/data windows,
source/session identity, cancellation and publication/lease authority. Caller
labels/receipt hashes and mutable FrozenDatasets containers cannot substitute
for this compatibility proof. No PR43 source or working schema change is imported.
Exact reviewed HEAD/tree/blob/disposition resides in READONLY_SELECTIVE_IMPORT.md
and target-cycle-provenance.json. Source branches remain unchanged.

## Grid negative controls and package

Nine added fixture cases exercise source replacement between path preflight and
SQLite open, later-store mutation after the first cut, resealed row identity/
epoch/boolean aliases, and revision selection just before/at availability39/40.
All9 pass against existing production logic; no product defect or artificial RED
is claimed. Initial monkeypatch argument collision and open SQLite fixture handle
were harness errors, preserved separately. New fixture/writer connections close explicitly.
The full exporter file74tests passed without skips/deselection. Retained source
seals cannot establish authentic producer history; remote Grid main remains
d537d525296ef34f727996e240ae6c60102c6082 and native historical truth BLOCKED.

Packaged API omission reproduced1failed/1passed, then the runtime roster includes
the reviewed API. A fresh isolated packaged interpreter exercises its default
capabilities without a listener/DB. Total runtime sources53. Integrated targeted
verification150passed (package/API/funding/G0); final exact-HEAD full tests and
hosted artifacts are separately required. New mandatory manifest1474nodes plus
47explicit platform requirements equals1521collected, disjoint and exhaustive.
WindowsPowerShell5.1 cases are required in Windows regression; unavailable Linux
executables are not converted into mandatory gate PASS.

## Target protocol and owner G1 boundary

TARGET_G0_EVIDENCE_PROTOCOL.md and TARGET_G0_COMMAND_MANIFEST.template.json specify
exact structured commands, target/tool pins, dependency observations, private
process/port/DB ownership ledger, resources, network/operation matrix and STOP.
They contain no target identity or authorization. Active LS5/PC4 have no allowed
operations. Target-bound manifest completion and its hash/owner admission occur
outside the release ZIP to avoid self/package hash cycles. No protected host is
silently chosen as the disposable VM. No remote discovery, DB connections,
Torch/native execution, installations, ACL/firewall changes or cleanup is admitted.

Final delivery carries an external unsigned owner-v2 inference-only template
binding exact source/tree/binary/package/input hashes. Owner/key/VM/nonce/expiry
remain unset. Independent target G0, complete native qualification and separately
signed owner authorization are required; a signature cannot repair missing native
controls. Previously blocked native implementation/review is not resumed.

## Readiness and findings

| Area | Result |
|---|---|
| Strattester | New software paths independently reviewed; fresh exact-HEAD CI required |
| G0 | PLAN_READY_TARGET_EVIDENCE_BLOCKED |
| API | BLOCKED_READ_ONLY_BOUNDARY; successful result/provenance producer deferred |
| Funding | SIGNATURE_VERIFIED_ONLY; historical truth BLOCKED; runtime NOT_ENABLED |
| Grid | Fixture negatives pass; native historical/coherence truth BLOCKED |
| OOS | Real independently attested multi-market OOS BLOCKED |
| GPU / full AlphaFold parity | BLOCKED_NOT_EXECUTED / NOT_PROVEN |
| Native sandbox | Full research isolation BLOCKED; stopped stage not resumed |
| Physical G1 | NOT_AUTHORIZED |
| Trading | NO-GO |

No new confirmed P0. P1 external blockers: trusted source history/coherence and
funding/fill completeness; real OOS/GPU/upstream evidence; independent owner/
producer provisioning; actual target G0; loaded-image/namespace/deny-all egress/
resource/crash guarantees; source-owned result/report/lease binding; independent
QA and exact owner authority. P2 corrected collector evidence/redaction/shape,
proposed API path admission and package omission. Actual credential exposure,
physical bypass or trading authorization was not demonstrated. Power-loss/VM
rollback durability and exchange ledger/notional/rounding remain unqualified.

`PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED`;
`PHYSICAL_G1=NOT_AUTHORIZED`; `TRADING=NO-GO`;
`PRODUCTION_DB_MUTATIONS=FORBIDDEN`; `MAIN_MERGE=FORBIDDEN`.
