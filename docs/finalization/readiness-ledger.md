# Final integration engineering ledger

Baseline PR21: 5d715987d03d4a26d31a48e9767697bbd171cd33. Current source identity
is `git rev-parse HEAD` / `git rev-parse HEAD^{tree}`; CI artifacts bind that
exact head. This ledger never transfers older PASS to newer source.

## Completed engineering phases

* A: audited PR15–30 and source repositories; source-pr-inventory.json retains
  exact heads/trees, commits/files and observed runs. New PR31–34 heads are in
  new-source-heads.json. Runtime architecture and ownership are documented.
* B/C: selective -x imports from PR32 (independent tests), PR33 (sealed export),
  PR34 (session/CLI/report), PR31 (native components). Per-file source blobs,
  reasons/contracts and compatibility are in source-import-provenance.json;
  the nested model/math manifest also records original PR18/23/29 blobs.
* D: read-only qualified historical profile exporter, SQLite WAL and real
  disposable PostgreSQL MVCC, shard/epoch/seal checks, bounded cursor/bytes,
  cancellation and immutable replay. Actual Grid missing historical facts
  fails before source access. No producer history has been fabricated.
* E: additional mechanism/math differential/gradient regressions, explicit
  externally pinned sessions, research registry opt-in, static HTML/SVG/CSV.
* F: deterministic native executable and restricted token/job/suspended owned
  probes/handle confinement/direct TCP WFP components tested in disposable
  hosted Windows. Full arbitrary research launcher is NOT implemented; it
  refuses with exit78 before research process creation.
* G: exhaustive CPU node manifests refreshed; platform requirements recorded
  separately. Mandatory compiled-native workflow is reused at common HEAD.
  Failure/cancellation of either engineering or native jobs fails aggregation.
* H/I: fresh independent review found and fixed public fixture owner-key misuse
  and packaged native build layout, both RED→GREEN. External owner signature
  verifier and reproducible public software fixture package added. Read-only
  G0 and external owner-signable plan documented; no physical G1 authorized.

## Findings and disposition

| Priority | Finding | Disposition |
|---|---|---|
| P0 | No newly confirmed active P0 in this cycle | Not a claim of absence of unknown defects |
| P1 | Native arbitrary research isolation incomplete: filesystem namespace, DNS proxy/UDP, descendants, output, owner trust verifier | OPEN; launch fails closed, Windows sandbox and G1 BLOCKED |
| P1 | Actual Grid schemas do not prove historical first availability/revision/coherence facts | OPEN external producer capability; native Grid export BLOCKED |
| P1 | PR23 unsigned snapshot dispatch can bypass producer attestation | Rejected source runtime; stronger integration retained |
| P1 | PR29 report checker accepts fabricated basename-only node identities | Rejected validator/workflow; exact-node root aggregator retained |
| P2 | Public RFC fixture key accepted for owner signature verification | FIXED: byte-level known-key denial; ephemeral test keys; 2RED then24GREEN including signature suite |
| P2 | Packaged native build script misplaced relative to C# sources | FIXED: preserve source/scripts layout; 1RED then15GREEN package/owner tests |
| P2 | Source PR22 stale triangle oracle and PR18 Decimal precision dependence | Rejected weaker collision; imported useful oracle precision fixed |
| P2 | CLI prediction does not itself drive model retraining and ledger evaluation | Separate explicit experiment path under development; do not claim full CLI chain until verified |
| P2 | Offline dependency manifest is versions/licenses, not complete hash-locked wheelhouse | OPEN packaging limitation; no automatic install |
| P3 | Temporary interrupted/test compiler directories retained | Evidence retained; guarded cleanup manifest required, no broad recursive removal |

## Validation observed before publication

Correct local environment: Python3.12.10, Torch2.14.1+cpu, NumPy2.5.4,
psycopg3.3.6. Full combined tests+research: 1157 passed, 12 skipped,
25 successful subtests (final-candidate.json/xml). This run preceded the
packaged-script path fix; targeted post-fix package+owner: 15 passed.
The final exact HEAD must be rerun through CI. Skips include CUDA2,
compiled broker6, hosted junction1 and unavailable local symlink3; none
qualifies the corresponding mandatory native/GPU requirement.

Source PR31 run40341527747 passed component tests on source2942a3e, binary
SHA256 5ad55022dc2c915cf83917979ddeb6e4872b7cc39ae7e39ad7c7abc3022829ef.
Earlier native failures40340988757/40341275478 were actual CPU query buffer
and WFP indexed flag issues, fixed without dropping assertions. This source
evidence is not a PASS for the final integration head.

## Readiness policy

STRATTESTER_SYSTEM_READINESS=BLOCKED_PENDING_COMMON_HEAD_CI_AND_EXTERNALS

ALPHAFOLD_MODEL_READINESS=CPU_SOFTWARE_VALIDATION_ONLY

GRID_SNAPSHOT_READINESS=QUALIFIED_FIXTURE_PROFILE_ONLY_NATIVE_GRID_BLOCKED

ML_OOS_READINESS=BLOCKED_NO_VERIFIED_REAL_OOS

WINDOWS_SANDBOX_READINESS=BLOCKED_COMPONENTS_ONLY

GPU_READINESS=BLOCKED_NO_REAL_GPU_EXECUTION

PHYSICAL_G0_READINESS=LOCAL_READ_ONLY_INVENTORY_ONLY_TARGETS_UNQUALIFIED

PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION=NO_GO

TRADING_READINESS=NO_GO

No source file, synthetic metric, owner signature alone or green workflow can
clear missing native controls, GPU qualification, producer facts or real OOS.
System acceptance intentionally remains BLOCKED even when engineering passes.
