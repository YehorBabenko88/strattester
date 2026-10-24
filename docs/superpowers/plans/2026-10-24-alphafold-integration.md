# AlphaFold Financial Integration Implementation Plan

> Execute inline with superpowers:executing-plans. User approved the design and continuous execution in PR21 comment 6385378621; no repeated approval handoff.

**Goal:** Tested offline integration candidate with honest blocked real-data/GPU acceptance.
**Architecture:** Import pinned components by path, preserve provenance, build a separately named connected structural model and immutable data boundary, deterministic safe checkpoints, and same-HEAD evidence gates.
**Tech Stack:** Python >=3.11, CPU PyTorch, pytest, JSON tensor checkpoints (no pickle), SQLite test fixtures, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-10-24-alphafold-integration-design.md approved at 9778e79cb3dbe49b9e88dccb05acf2286374a87a.

## Global Constraints

Use integration/alphafold-financial-system and Draft PR21 only. No main merge, production DB writes, orders, biological weights, arbitrary deserialization, fabricated snapshot epochs or success claims. Exact SHA and test evidence per milestone; keep real data and GPU BLOCKED without actual evidence.

## Review Focus

- A mask must exclude future dependencies through OPM, triangles and recycling, not only row attention (Task 3).
- Admission must precede normalization/projection/parameter allocations, including MSA S and dtype/backward (Tasks 1,3).
- Equal cutoffs cannot certify independent mutable shards; reject unsupported real DDL (Task 2).
- Checkpoint content hash is not producer trust; load only caller-pinned bounded tensor JSON with strict shape/schema and finite values (Task 4).
- CI skips, missing reports, stale SHA and failed/cancelled jobs never count as PASS (Task 5).

### Task 1: Pinned import and immediate regressions

Files: import paths listed in docs/integration/evidence/inventory.json from pinned PR16,17,18,19,20; create docs/integration/component-origins.json; add tests/research/test_alphafold_integration_regressions.py.
Interfaces: existing encode_market; build_outer_product_mean; financial model remains experimental until Task3 supplies connected build_structural_model.
- [ ] Export only audited changed files: PR16 includes PR15; PR20 overrides shared hardened paths. Record source blob and SHA per path.
- [ ] Run imported baseline with CPU torch; retain JUnit and report any skips/failures.
- [ ] RED: encode_market rejects fractional/string/bool timestamps; OPM rejects large S before norm; negative/empty dimensions rejected. GREEN: strict timestamp validation and byte-aware MSA admission before allocations.
- [ ] Verify relevant suites and commit import/fixes; disconnected graph and mandatory coverage fixed in Tasks3/5.

### Task 2: Immutable data and mathematical contract

Files: strattester/research/financial_contract.py, financial_snapshot.py; tests/research/test_financial_contract.py, test_financial_snapshot.py; imported research/math_contract_reference.py.
Interfaces: frozen Instrument/Bar/Snapshot/Prediction; explicit timestamp conversion; canonical_digest; load_snapshot(path,expected_sha256,trusted_producers,max_bytes); read_sqlite_snapshot rejects missing contract columns.
- [ ] RED: invalid units/types/NaN, gaps, incomplete bars, changed provenance/hash, mismatched epochs, future availability and actual legacy DDL rejected; synthetic WAL writer cannot alter open read view.
- [ ] GREEN: bounded immutable JSON snapshot loader, strict schema and causal validation; fail closed on unsupported history. No production opener.
- [ ] Verify math independently (Decimal log oracle, sample variance, train-only transform); commit.

### Task 3: Connected structural model

Files: strattester/research/financial_structural_model.py; tests/research/test_financial_structural_model.py; reuse PR16 row/OPM/pair operators.
Interfaces: StructuralConfig; build_structural_model(config) -> nn.Module accepting [B,S,N,C] and binary mask, emitting [B,2] Gaussian mu/scale. Whole-window prediction at one explicit origin; future/unavailable inputs masked before mixing.
- [ ] RED: required operator hooks execute, all active trainable parameters get finite gradients, masked-input perturbations leave output unchanged, recycle count honored, shape/parameter/workspace budgets reject hostile inputs.
- [ ] GREEN: column attention, MSA transition, row/pair exchange, single extraction and bounded recycling with existing row/OPM/triangle/transition operators; Gaussian positive bounded scale.
- [ ] Verify explicit-index operator references and integrated gradients/causality; commit.

### Task 4: Reproducible offline experiment

Files: strattester/research/financial_training.py, financial_checkpoint.py, financial_evaluation.py; tests/research/test_financial_training.py, test_financial_checkpoint.py, test_financial_evaluation.py.
Interfaces: fit_structural(model,X,y,mask,seed,steps,cancel); save_checkpoint/load_checkpoint with caller-pinned digest; evaluate ledger with explicit costs and liquidation; research experiment is labelled synthetic unless verified data supplied.
- [ ] RED: actual weights change; repeat seed reproduces state/predictions; fresh-process reload reproduces inference; tamper/oversize/shape/NaN rejected; cancellation registers no checkpoint; overlapping labels rejected; literal round-trip fee/exit ledger; randomized controls and holdout checks.
- [ ] GREEN: bounded deterministic optimizer loop, atomic JSON tensor checkpoint, independent baseline/control OOS accounting with purged windows and bootstrap intervals.
- [ ] Verify local artifact roundtrip and synthetic E2E without calling it real OOS; commit.

### Task 5: Mandatory gates and adversarial E2E

Files: scripts/financial_gate.py, strattester/research/financial_acceptance.py, .github/workflows/financial-integration.yml; tests/research/test_financial_acceptance.py, test_financial_offline_e2e.py; modify CPU script to include financial/security suites.
Interfaces: gate reports bind exact commit, gate identity, required node IDs and actual accounting; aggregate rejects missing/skipped/stale evidence and external BLOCKED gates.
- [ ] RED: missing torch/file/test, critical skip/xfail/deselection, tampered/stale report and cancelled workflow cannot pass; deny socket and production access through offline pipeline.
- [ ] GREEN: separate core/data/math/CPU/training/security/integration jobs, JUnit+JSON artifacts, always-run fail-closed aggregator; GPU and real OOS explicit BLOCKED.
- [ ] Run full suite locally, commit and push; collect exact run/job evidence and update PR21.

### Task 6: Independent review and final evidence

Files: docs/integration/stage-reports.md, mechanism mapping, final candidate evidence and outputs/ report.
- [ ] Fresh-context whole-branch review per executing-plans; reproduce and fix actionable issues with RED/GREEN tests.
- [ ] Re-run affected gates/full suite after changes; push; bind local/hosted evidence to final exact SHA and record all blockers.
- [ ] Verify source PR heads unchanged and PR21 Draft. Do not mark overall acceptance PASS while real data/GPU/reference requirements remain blocked.
