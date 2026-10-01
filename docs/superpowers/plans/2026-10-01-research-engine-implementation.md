# Research Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a causal historical research engine that evaluates level, SMC, POC and volatility-conditioned hypotheses without look-ahead or survivorship bias.

**Architecture:** Extend the existing standalone foundation with lifecycle/coverage registries, richer historical datasets, a versioned causal feature layer, causal execution/trade journal, and chronological statistical evaluation. Existing scheduler and strategy contracts remain the orchestration boundary; missing data becomes explicit prerequisites or coverage classifications.

**Tech Stack:** Python 3.11+, SQLite, requests, psutil, pytest; optional PostgreSQL remains metadata/state only.

**Spec:** `docs/superpowers/specs/2026-10-01-research-engine-design.md`

## Global Constraints

- Every derived feature exposes `event_time` and `known_at`; consumers must reject future knowledge.
- Signals formed at bar close cannot market-fill before the next bar.
- Delisted history is retained; new instruments receive no synthetic pre-listing history.
- `PARTIAL_HISTORY` is reported separately and never silently pooled into primary `COMPLETE_HISTORY` aggregates.
- POC output always identifies `POC_PROXY` or `TRADE_POC`.
- Never fabricate unavailable historical L2/orderbook or liquidation data.
- Validation is chronological; no random time-series train/test split.
- Runtime data remains outside immutable releases under `C:\ProgramData\Strattester`.

## Review Focus

- Future rows appended to a dataset must not alter already-known historical signals or trades; pin with prefix-invariance tests in Tasks 4 and 8.
- Exchange disappearance must not delete a delisted symbol or its history; pin in Task 2.
- Partial delisted data must never leak into COMPLETE primary aggregates; pin in Tasks 3 and 10.
- Newly listed symbols must not acquire pre-listing candles/features; pin in Tasks 2 and 3.
- POC/volatility calculations at T must not consume trades/bars after T; pin in Tasks 6 and 7.

---

### Task 1: Rich Historical Dataset Contracts and Schema

**Files:**
- Create: `strattester/marketdata/datasets.py`
- Modify: `strattester/marketdata/schema.py`
- Modify: `strattester/strategies/base.py`
- Test: `tests/marketdata/test_rich_schema.py`
- Test: `tests/strategies/test_requirements.py`

**Interfaces:**
- Produces: `DatasetKind`, extended `DataRequirement`, versioned schema tables for mark/index/premium, OI, funding, long/short and public-trade aggregates.

- [ ] Write failing tests proving every required dataset has an explicit schema/requirement and unsupported L2 remains unavailable.
- [ ] Run focused tests and verify failure.
- [ ] Implement dataset enum/contracts and additive SQLite schema migration.
- [ ] Run focused tests and full pytest; expect PASS.
- [ ] Commit: `feat: add rich historical dataset contracts`.

### Task 2: Instrument Lifecycle Registry

**Files:**
- Create: `strattester/marketdata/instruments.py`
- Modify: `strattester/marketdata/schema.py`
- Test: `tests/marketdata/test_instruments.py`

**Interfaces:**
- Produces: `InstrumentStatus`, `InstrumentRecord`, `InstrumentRegistry.reconcile(exchange_snapshot, observed_at)`, `eligible_at(symbol, timestamp)`.

- [ ] Write failing tests for ACTIVE->SUSPENDED/DELISTED retention, new listing, availability intervals and no deletion.
- [ ] Add test proving a new symbol is ineligible before first availability.
- [ ] Implement registry and reconciliation with persisted lifecycle intervals.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: track instrument lifecycle without survivorship bias`.

### Task 3: Coverage Audit and COMPLETE/PARTIAL Classification

**Files:**
- Create: `strattester/marketdata/audit.py`
- Modify: `strattester/marketdata/coverage.py`
- Modify: `strattester/engine/executor.py`
- Test: `tests/marketdata/test_audit.py`
- Test: `tests/engine/test_requirements_coverage.py`

**Interfaces:**
- Produces: `HistoryClass.COMPLETE_HISTORY|PARTIAL_HISTORY|INSUFFICIENT_HISTORY`, `CoverageAudit`, prerequisite sync decisions.

- [ ] Write failing tests for complete active history, unrecoverable delisted gap -> PARTIAL, and insufficient mandatory dataset.
- [ ] Add tests preventing pre-listing coverage and preventing PARTIAL from satisfying a COMPLETE-only run.
- [ ] Implement audit/classification and executor prerequisite integration.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: classify research history coverage`.

### Task 4: Causal Feature Core

**Files:**
- Create: `strattester/research/causal.py`
- Create: `strattester/research/__init__.py`
- Test: `tests/research/test_causal.py`

**Interfaces:**
- Produces: `CausalFeature(event_time, known_at, kind, value, version)`, `CausalView.at(decision_time)`.

- [ ] Write failing tests rejecting `known_at > decision_time`, confirmed-pivot timing and prefix invariance after future rows are appended.
- [ ] Implement immutable causal feature/value contracts and filtered views.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: enforce causal feature visibility`.

### Task 5: Level and SMC Feature Engines

**Files:**
- Create: `strattester/research/levels.py`
- Create: `strattester/research/smc.py`
- Test: `tests/research/test_levels.py`
- Test: `tests/research/test_smc.py`

**Interfaces:**
- Produces causal completed-period levels, confirmed swings, BOS, CHOCH, sweep, order-block and FVG events with versioned definitions.

- [ ] Write failing fixtures for completed 1H/4H/D levels and prior-period availability.
- [ ] Write failing fixtures for swing/BOS/CHOCH/sweep/OB/FVG confirmation timing.
- [ ] Implement level engine, then SMC engine without future pivots.
- [ ] Add combination-event tests for OB+FVG and sweep+BOS.
- [ ] Run full suite; expect PASS.
- [ ] Commit: `feat: add causal level and smc features`.

### Task 6: POC and Volume Profile Research

**Files:**
- Create: `strattester/research/volume_profile.py`
- Test: `tests/research/test_volume_profile.py`

**Interfaces:**
- Produces: `POCMode.POC_PROXY|TRADE_POC`, `VolumeProfileSnapshot(poc, vah, val, known_at, mode, ...)`.

- [ ] Write failing tests that distinguish proxy from public-trade profiles and require mode labels.
- [ ] Add prior-day/week and rolling-window tests proving rows after snapshot time do not affect the profile.
- [ ] Implement POC/VAH/VAL, migration and value-area width snapshots.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: add causal volume profile research`.

### Task 7: Volatility Observatory

**Files:**
- Create: `strattester/research/volatility.py`
- Test: `tests/research/test_volatility.py`

**Interfaces:**
- Produces: `VolatilitySnapshot`, `VolatilityRegime`, versioned ATR%, realized/Parkinson/range/volume-turnover expansion and prior-history percentile features.

- [ ] Write failing tests for metrics and VERY_LOW/LOW/NORMAL/HIGH/EXTREME classification.
- [ ] Add prefix-invariance test proving future volatility cannot reclassify an old snapshot.
- [ ] Implement observatory using only prior observations for percentiles.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: add causal volatility observatory`.

### Task 8: Causal Execution Simulator and Trade Journal

**Files:**
- Create: `strattester/research/execution.py`
- Create: `strattester/research/journal.py`
- Test: `tests/research/test_execution.py`
- Test: `tests/research/test_journal.py`

**Interfaces:**
- Produces: versioned `ExecutionPolicy`, `Signal`, `ResearchTrade`, append-only journal records with lifecycle/coverage/volatility/POC metadata.

- [ ] Write failing tests for next-bar market entry, next-bar limit eligibility, SL-first ambiguous 1m bar, gaps, fees and configurable slippage.
- [ ] Add prefix-invariance test: future candles cannot change already closed trades.
- [ ] Implement execution simulator and journal.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: add causal execution and trade journal`.

### Task 9: Research Strategy Library and Legacy 28 Regression

**Files:**
- Create: `strattester/strategies/builtin/research_levels.py`
- Create: `strattester/strategies/builtin/research_smc.py`
- Create: `strattester/strategies/builtin/research_poc.py`
- Create: `strattester/strategies/builtin/research_volatility.py`
- Modify: `strattester/strategies/builtin/legacy_grid.py`
- Test: `tests/regression/test_legacy_28.py`
- Test: `tests/research/test_hypotheses.py`

**Interfaces:**
- Produces independent hypothesis configurations and ablation/control variants; ports all 28 legacy variants against pinned fixtures.

- [ ] Pin legacy fixtures and failing expected trade/result tests for all 28 variants.
- [ ] Implement full legacy engine preserving old semantics.
- [ ] Add hypothesis configs for levels, SMC, POC and volatility-conditioned controls/ablations.
- [ ] Run regression and full suite; expect PASS.
- [ ] Commit: `feat: add research hypotheses and legacy regressions`.

### Task 10: Statistical Evaluator

**Files:**
- Create: `strattester/research/statistics.py`
- Create: `strattester/research/reporting.py`
- Test: `tests/research/test_statistics.py`
- Test: `tests/research/test_reporting.py`

**Interfaces:**
- Produces aggregate metrics, breakdowns by volatility/lifecycle/liquidity/trend/setup, and separate COMPLETE/PARTIAL reports.

- [ ] Write failing deterministic-journal tests for expectancy, PF, drawdown, MAE/MFE, R, holding time, streaks and net/gross costs.
- [ ] Add tests that COMPLETE primary output excludes PARTIAL and that volatility cross-tabs preserve sample counts.
- [ ] Implement evaluator/report model.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: add research statistics and regime reporting`.

### Task 11: Chronological Validation, Bootstrap and Monte Carlo

**Files:**
- Create: `strattester/research/validation.py`
- Create: `strattester/research/resampling.py`
- Test: `tests/research/test_validation.py`
- Test: `tests/research/test_resampling.py`

**Interfaces:**
- Produces chronological train/validation/test and walk-forward folds, frozen selected parameters, bootstrap CIs and seeded Monte Carlo trade-sequence distributions.

- [ ] Write failing tests that folds never overlap or use future rows and test parameters are frozen.
- [ ] Write deterministic seeded bootstrap/Monte-Carlo tests.
- [ ] Implement validation/resampling.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: add walk forward and resampling analysis`.

### Task 12: Exchange Universe Discovery and Rich Sync

**Files:**
- Modify: `strattester/marketdata/bybit_client.py`
- Modify: `strattester/marketdata/sync_engine.py`
- Create: `strattester/marketdata/universe_sync.py`
- Test: `tests/marketdata/test_universe_sync.py`
- Test: `tests/marketdata/test_rich_sync.py`

**Interfaces:**
- Consumes lifecycle and dataset contracts.
- Produces periodic exchange reconciliation and idempotent sync jobs per recoverable dataset/range.

- [ ] Write failing tests for newly listed, disappeared/delisted, 403 isolated failure, pagination, reverse chronological API rows and closed-data-only ingestion.
- [ ] Add test that unrecoverable delisted gaps remain PARTIAL without destructive deletion.
- [ ] Implement universe/rich-data client and sync paths.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: reconcile exchange universe and rich history`.

### Task 13: Strategy Fingerprint and Reproducibility Metadata

**Files:**
- Modify: `strattester/strategies/base.py`
- Modify: `strattester/engine/executor.py`
- Test: `tests/strategies/test_fingerprint.py`

**Interfaces:**
- Produces fingerprint including strategy code/content identity, definition/version, requirements and feature-definition versions.

- [ ] Write failing test proving a code-content change changes identity even if class/module name is unchanged.
- [ ] Implement deterministic source/content fingerprint and run metadata.
- [ ] Run tests/full suite; expect PASS.
- [ ] Commit: `feat: make research runs reproducible`.

### Task 14: Research Orchestration and Acceptance

**Files:**
- Create: `strattester/research/runner.py`
- Modify: `strattester/runtime/bootstrap_worker.py`
- Create: `docs/research.md`
- Test: `tests/e2e/test_research_pipeline.py`

**Interfaces:**
- Produces end-to-end run from audited historical data through causal features/execution to COMPLETE/PARTIAL regime-aware reports.

- [ ] Write E2E fixture containing an active symbol, a delisted partial symbol and a newly listed symbol.
- [ ] Assert no pre-listing trades, no future-feature leakage, separate COMPLETE/PARTIAL reports and volatility-stratified results.
- [ ] Wire runner to existing scheduler prerequisites and durable state.
- [ ] Document research semantics and output interpretation.
- [ ] Run `python -m pytest -v`; expect all tests PASS on supported CI matrix.
- [ ] Commit: `feat: integrate causal research pipeline`.
