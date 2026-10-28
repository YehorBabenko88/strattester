# Six-direction physical readiness program

Baselinef60869686a51693799b4844a1af49c9b39ba45d5/tree0f7626787ec835a9a945a8e576d19181044f23ec.
Six isolated branches/worktrees; only Lead modifies PR21. Four available execution
slots required two waves;6workstreams were not falsely reported as6simultaneous
workers. Native worktree API could not resolve nested repo; manual Git worktrees
outside checkout used. No old worktree/native stage reused or resumed.

| Direction | Branch | Draft PR | Source HEAD |
|---|---|---:|---|
| Windows G0 | parallel/20261027-g0 |49|e900087274410e4e0966c540612c35e3321119e5|
| Grid | parallel/20261027-grid |48|7125b3d4caff3814629625e59d66dc5b299cc609|
| ML/OOS | parallel/20261027-ml |51|e4e8f19d9b54c35851486466b062a7d9fdc11839|
| AlphaFold/Math | parallel/20261027-math |54|988b42c170b822f6aef37e63e9fb5c9f4806b0c0|
| Trust/Replay | parallel/20261027-trust |52|50182f50b9fc041e67d60bbc80f7f735d21363b9|
| QA/CI/Packaging | parallel/20261027-qa |53|dedc98382ee33787de476f44dd00e20864be881b|

Exact source trees,changed-file blob IDs,import commits,ownership and reasons are
in parallel-program-provenance.json. Lead independently inspected diffs and reran
each lane's new targeted tests before sequential cherry-pick. No blind branch
merge. Source CI snapshots and final exact-head raw/JUnit/artifact proofs are
published separately after final commit; incomplete source CI is not calledPASS.

G0: pure missing/invalid/unverified preflight, no IO or target collection. New
explicit research command reads two externally pinned bounded local inputs:

```text
python -m strattester.research_cli inspect-g0-preflight --selection <LOCAL_SELECTION> --selection-sha256 <EXTERNAL_PIN> --capture <LOCAL_CAPTURE_PLAN> --capture-sha256 <EXTERNAL_PIN>
```

AlwaysBLOCKED/exit2. No raw private values echoed; no path/receipt dereference.
This is declared prerequisite review, not physical identity/ACL/storage proof.
Actual source/read-only collector is unchanged. VM NOT_SELECTED; all10physical
groups NOT_COLLECTED; target pathsNOT_AUTHORIZED,rollbackNOT_VERIFIED,delivery
NOT_DEFINED. Future operator capture requires independent30s/8MiB bounds and
2GiB free-disk floor,private ownership/encryption/quota/namespace evidence.

Grid: complete normalized SQLite schema objects now pinned, including rejecting
extra view/index/trigger. Producer main d537d525296ef34f727996e240ae6c60102c6082
still lacks authentic first availability/revisions/funding/cross-store epoch facts.
Read-only source DDL review and disposable SQLite tests do not create history.

ML: OOS control baselines reject training events at/after first test globally,
including cross-instrument future rows. Label/purge/holdout prerequisites remain
separate; this does not prove arbitrary callers' training labels are leakage-free.
Synthetic validation is software only; real OOS and authenticated funding remain
BLOCKED/runtimefundingNOT_ENABLED.

Math: nearby positive price ratios use log1p to avoid cancelling adjacent prices
at extreme numeraires; large ratios retain separate logs to avoid overflow.
Timeframe rejects before modulo/checkpoint path. Decimal exact-input oracles,
mask/gradient/triangle/recycle suites are software evidence. Existing checkpoint
predictions may change across source revisions; no cross-revision bitwise claim.
GPU/full upstream equivalence remainBLOCKED.

Trust: G0 receipt verifier now requires exact pinned OpenSSLVerifier, matching
existing owner contract. Arbitrary Python runtime/class mutation is not contained
by this check. It is a P2 API contract tightening, not demonstrated physical
admission exploit. Signatures still prove assertions only; durable G0 replay and
rollback-resistant independent registry remain unimplemented/externalBLOCKED.

QA: versioned standalone audit_qualification_artifact.py/library checks3report
members without extraction,external archive digest/head/run/repository/roster,
bounded ZIP32 deflate EOF/CRC/length/descriptors,raw setup/call/teardown,Junit
counter/node consistency. Independent reviewRED3failed/14passed ->GREEN17passed.
Successful subtest assertion surplus is recorded,never counted as parent nodes.
ConsistencyVERIFIED_ONLY remainsBLOCKED/authenticityUNVERIFIED_SELF_REPORT; no
trusted job execution or external/physical authority created.

P0:newconfirmednone. P1:fixed future-training control defect; producer/owner/VM/
native/OOS/GPU/full parity/physical proof missing; PR43 deferred. P2:fixed schema
membership,feature precision/timeframe,verifier contract and QA consistency gaps.
Source failures,collection/setup mistakes,deselections and sourceCI cancellations
are retained separately. No skipped test promoted toPASS.

Native source/build/workflows unchanged. Existing hosted component jobs are not
physical G1 or full isolation. No production DB/service,activeLS5/PC4,trading,
VM provisioning,physical collection,G1 Execute/Cleanup or deployment operation.
STOP and cleanup protocols remain review-only; no automatic recursive cleanup or
nonce-history deletion. Historical Ubuntu timeout originalFAIL/retry remain
separate; no deadline increase or retry-as-fix claim.

STRATTESTER_SYSTEM_READINESS=EXACT_HEAD_CI_REQUIRED;GRID_SNAPSHOT_READINESS=BLOCKED;
ML_OOS_READINESS=BLOCKED;ALPHAFOLD_MODEL_READINESS=CPU_SOFTWARE_ONLY;
WINDOWS_G0_READINESS=PLAN_READY_TARGET_EVIDENCE_BLOCKED;
WINDOWS_NATIVE_ISOLATION_READINESS=BLOCKED;PHYSICAL_G1_AUTHORIZATION=NOT_AUTHORIZED;
DEPLOYMENT=NO-GO;TRADING_READINESS=NO_GO.
