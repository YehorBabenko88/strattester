# Data-First PR62 integration implementation plan

> For agentic workers: execute inline with superpowers:executing-plans; use a fresh final code review. No new physical execution authorization is implied.

**Goal:** Integrate reviewed PR62 into Draft PR21 with fresh exact-head evidence and explicit financial snapshot boundaries.

**Architecture:** Preserve the explicit DataFirstScheduler entry point and its category-qualified registry, closed-history planner, bounded SyncEngine, SQLite read snapshot and atomic state/result ledger. Keep financial signed-snapshot inference behind FinancialResearchContext; candle readiness is not historical attestation. No ordinary CLI auto-activation.

**Tech stack:** Existing Python3.11–3.13 CI, SQLite, synthetic Bybit transport. Local source tests use existing development Python3.12; no local Torch/model execution.

**Spec:** Owner's ten integration requirements in this chat; approved source design in docs/readiness/DATA_FIRST_SCHEDULER.md from PR62.

## Global constraints

- LS5_CONNECTED_SYNC=NOT_AUTHORIZED; PHYSICAL_G1=NOT_AUTHORIZED; TRADING=NO-GO.
- No main merge, production DB/service mutation, physical smoke run or blocked native stage.
- Base PR21 HEAD57d560a/tree6bd1527; source PR62 HEADbceb60f/tree576f907 verified from remote refs before changes.
- Preserve original source commits/blob hashes and historical CI separately. Never transplant1845PASS.

## Review focus

- Financial strategy accidentally enabled in generic candle scheduler must not execute.
- Concurrent writer changes between validation and execution must not change admitted data.
- Fresh scheduler instances must not replay committed output or uncertain RUNNING side effects.
- Discovery omissions must not fabricate delisting history; missing required event history remains BLOCKED.
- Rate/page limits must bound the entire future invocation, not only one tick.

## Task1: source review and import

- [x] Pin both remote HEAD/tree and comments; compare all22 changed paths and critical interfaces.
- [x] Verify source-only scoped211 tests in isolated integration worktree after cherry-pick with -x.
- [x] Preserve compatible runtime, disabled/readiness gates, tests and mandatory manifest deltas; do not import any native source or weaken signed contracts.
- [x] Record per-file source blob/SHA256 and rationale under docs/readiness.

## Task2: integration regressions and confirmed defects

Files: tests/engine/test_data_first_integration.py; affected runtime only when a failing test proves a defect; scripts/financial-gate-manifest.json.

- [x] Test actual LegacyGridStrategy, partial/new instruments, delisted archive, cancellation/restart and concurrent writes on disposable SQLite with no network.
- [x] Test actual financial registration default-disabled, explicit enable without signed context fail-closed, and generic context rejection without invoking model code.
- [x] Reproduce any new admission/sync/publication defect RED before minimal fix; retain logs.
- [x] Register every new required node explicitly; keep existing roster intact except documented source rename.

## Task3: review, exact-head CI and handoff

- [ ] Resolve independent source review findings, rerun scoped source tests; full neural/system execution hosted only.
- [x] Document future network flow, all public endpoints, shared rate and total request/page/byte budgets, dedicated history root and exact writes. No real connection invocation on LS5.
- [ ] Commit and update integration Draft PR21 without main merge; source PR62 untouched.
- [ ] Collect exact-head Windows/Linux, DataFirst, financial, synthetic ML CI; verify original ZIP hashes, source/tree, required node sets, raw/JUnit, failed/skipped/deselected separately.
- [ ] Preserve acceptance BLOCKED and external history/OOS/GPU/native facts. Publish final readiness and immutable evidence.

## Ledger

Ruling: integrate into the existing PR21 branch after isolated review; no blind merge. Shared critical files have no textual conflict because source62 is based on the exact current21. FinancialResearchContext has no generic candle requirements; it cannot be automatically adapted without weakening signed provenance. Tests will preserve the boundary.

Source ledger:211PASS imported baseline; confirmed8FAIL/5PASS after fixture correction; redirect regression1FAIL; final226PASS release. Independent14-case adaptation review passed before redirect followup; final15-case review requested. New required integration nodes15, total1860. Budget formula explicitly applies to current fixed one-candle-requirement CLI only.
