# UNIFIED RELEASE — Stage 2 Strattester consolidation ledger (Issue #86)

Status: **PARTIAL MIGRATION / NO_GO**. Parent: YehorBabenko88/unified-system#111.

> MASTER #111 ownership change dated 2026-11-19 supersedes the previous strategy-ownership map: **Terminan owns all strategies, registration, experiments and execution simulation; Math owns domain mathematics; Grid owns exchange data; Unified owns service orchestration.** Strattester is a transition/source repository, **not** a second planned runtime.

## Frozen sources / proof scope

| Source | Exact SHA | Note |
|---|---|---|
| Strattester main | `37ff7e9d12a4d2dccd788fc493c28557dbe8bcea` | current default base inspected, not integrated |
| Strattester research PR #83 | `d6293f75db7fcc8eed0900521a1ba6bd46b3468e` | stacked candidate with actual implementation |
| Strattester security PR #84 | `731f325a505ff18720c550aa0dc762ed54dd537b` | pin-actions fix; not merged |
| Grid PR #288 | `a2495825a2c8f412749b62bb9ebda6f4f79fd8d4` | source-side candidate, not confirmed integrated |
| Terminan PR #83 | `e23abe3345379e41f979695136fd1261e3cbd238` | UI candidate, stacked, not merged |
| Math PR #117 | `d4bef309be3a78d790433bcd2d880927a20e32c0` | science candidate, not merged |
| **Terminan migration PR #88** | **`db979e5bc9ec6c0cb520df229781a533a2cf6d7b`** | **real Python code + regression tests**, draft |

## Explicit source -> target ownership and current state

| Strattester file:function / class | Dependencies / effects | Owner / target | Actual stage |
|---|---|---|---|
| `strattester/strategies/base.py:DataRequirement,StrategyDefinition,strategy_fingerprint` | dataset enum, SHA256/json/inspect | **Terminan** `terminan/contracts.py` | **MOVED in target Draft #88**; closed dataset strings remove old enum import; legacy still present |
| `strattester/strategies/registry.py:StrategyRegistry.register/discover/set_enabled` | StrategyDefinition | **Terminan** `terminan/contracts.py` | **MOVED in target Draft #88**; duplicate/version/identity tests; legacy still present |
| `strattester/strategies/builtin/research_common.py:HypothesisSpec,executable_hypotheses` | dataclass, typing | **Terminan** `terminan/contracts.py` | **MOVED in target Draft #88**; SPEC_ONLY gating tested; legacy still present |
| `strattester/strategies/builtin/{research_levels,research_poc,research_smc,research_scalp,research_volatility}.py` | research_common | **Terminan** strategy catalog | NOT MOVED: catalog spec mapping/parity pending |
| `strattester/strategies/builtin/legacy_grid.py:BacktestEngine,run_legacy_suite` | level/fee calculations, simulator | **Terminan** execution; **Math** numeric formulas | NOT MOVED: split/accuracy and source provenance pending |
| `strattester/engine/executor.py:execute_strategy,requirements_ready,StrategyContext` | strategy_fingerprint, store/coverage | **Terminan** experiment executor + **Grid** snapshot reader | NOT MOVED: execution/data coupling |
| `strattester/research/runner.py:ResearchRunner.run/_sync_definition` | SyncEngine and execute_strategy, DB writes | **Terminan** run orchestration + **Grid** acquisition | NOT MOVED: explicit writer coupling (P0) |
| `strattester/research/execution.py:simulate_trade,simulate_scale_trade` | Signal, ExecutionPolicy, OHLC and PnL | **Terminan** simulation + Math policy numeric | NOT MOVED: bar fill/SL/TP parity tests pending |
| `strattester/research/statistics.py:evaluate_trades` | PnL statistics, drawdown, expectancy | **Math** | NOT MOVED: finite/precision/parity review |
| `strattester/research/reporting.py:research_report` | evaluate_trades | **Terminan** report orchestration consuming **Math** | NOT MOVED |
| `strattester/research/result_persistence.py:persist_report_fenced` | ResultStore fenced result | **Terminan** result lifecycle; **Unified** optional custody | NOT MOVED: exactly-once and rollback |
| `strattester/persistence/result_store.py:ResultStore` | SQLite and filesystem result records | **Terminan/Unified decision PENDING** | KEEP existing data; never delete during migration |
| `strattester/marketdata/bybit_client.py:BybitClient.get/fetch_klines/fetch_linear_instruments` | requests, network, retries | **Grid** public Bybit client | NOT MOVED: producer and import graph |
| `strattester/marketdata/sync_engine.py:SyncEngine._sync_rows/sync_requirement` | Bybit, SQLite/market writes | **Grid** history ingestion | NOT MOVED: active direct writer |
| `strattester/marketdata/readiness.py:ensure_history/ensure_instrument_history` | SyncEngine, local store | **Grid** coverage; Terminan requests readiness | NOT MOVED: active fetch/write boundary |
| `strattester/marketdata/{sqlite_store,sharded_store,store_factory}.py` | persistent marketdata/shards | **Grid** canonical storage | KEEP historical data; export and source proof required |
| `strattester/marketdata/l2_recorder.py:L2AbsorptionDetector` | statistical L2 absorption computation | **Math** or Terminan source adapter; MASTER decision | NOT MOVED: NOT proven live recorder |
| `strattester/engine/{scheduler,jobs,resource_manager}.py` | worker allocation | **Unified** orchestration / Grid bounded execution | NOT MOVED: runtime call graph pending |
| `strattester/runtime/{lifecycle,service_manager,grid_handoff,worker}.py` | Windows/service/worker lifecycle | **Unified** | NOT MOVED: native recovery tests required |

Source-path references are exact observed code locations, **not** claims of exhaustive symbol inventory for every stacked branch.

## Actual changes versus remaining dual source

Terminan Draft PR #88 modifies **two existing files**, `terminan/contracts.py` and `tests/test_contracts.py`; **zero new services or modules**. Tests cover duplicate registration, version fingerprint, enabled state identity, rejected unknown dataset and declarative vs explicitly executable hypotheses. This introduces no DB writes, live exchange access or orders.

**This is a staged transfer, not final deduplication**: the Strattester originals remain used or possibly used by its existing tests/runtime. They must only be removed after Terminan imports and all legacy references have been migrated, source+target parity and rollback have been demonstrated, and MASTER confirms the removal map. This PR intentionally contains no deletion.

## Acceptance matrix / blockers

1. **P0**: Decide whether Grid absorbs all Strattester data and Strattester retires as a service. Grid & MASTER ACK required.
2. **P0**: Terminan #88 registry import consumers must be switched and validated; source files remain intact until an exact compatibility/preservation proof. No false claim of a completed migration.
3. **P0**: Mathematical formulas, scientific kernels, indicators and trading metrics move to Math alone. Needs independent precision and point-in-time parity.
4. **P0**: Full-history all-ref secret scanning and third-party dependency audit not completed. Treat security clearance as UNKNOWN.
5. **P0**: Proven real Bybit->Grid history/live->Terminan strategy->Math results with close-time, gap/seed/source receipts, restart, Windows/rollback not completed.
6. **P1**: Enumerate all open branch heads/PR dependencies, exact import/call graph, before/after lines of code, long-lived storage ownership and impact of native code.

Previous Strattester strategy-owner guidance is **withdrawn**. Do not merge PR #87/#88 or remove source while status is **NO_GO**.

## Stage 3 reconciliation — single Terminan strategy owner (2026-11-19)

**CRITICAL correction to all earlier Stage-2 rows above:** Terminan owner PR #87 had already migrated `DataRequirement`, `StrategyDefinition`, `StrategyRegistry`, `strategy_fingerprint` into `terminan/strategies.py` at SHA `08f3c12fdc2d989d8f13f757f73ecc298631089f`. My separate PR #88 duplicated these classes in `terminan/contracts.py`. This duplicate was detected and corrected **within the existing PR #88**, not by creating a third registry. Exact PR #88 target HEAD now `603ae1d9a05087a2640564885b0b47388980e9ff`: includes the exact canonical `terminan/strategies.py` blob + owner tests and makes `terminan/contracts.py` import those four symbols. Unique `HypothesisSpec/executable_hypotheses` stay as declarative SPEC_ONLY gating in contracts. Prior Stage-2 descriptions of `contracts.py` as primary registry owner are superseded.

### KEEP / MOVE / MERGE / DELETE actual ledger

| Source / target | Action | Verified now | Blocking evidence for deletion |
|---|---|---|---|
| `strattester/strategies/base.py:{DataRequirement,StrategyDefinition,strategy_fingerprint}` -> `terminan/strategies.py` | MOVE; KEEP source temporarily | Target source copied; canonical owner PR #87; PR #88 imports it | Live consumer call graph and provenance/parity on pinned source |
| `strattester/strategies/registry.py:StrategyRegistry` -> `terminan/strategies.py` | MOVE; MERGE duplicate | One canonical implementation **inside PR #88**; second definition in `terminan/contracts.py` removed | Cross-repo consumers, release/rollback acceptance |
| `strattester/strategies/builtin/research_common.py:{HypothesisSpec,executable_hypotheses}` -> `terminan/contracts.py` | MOVE; KEEP source temporarily | Target exists with SPEC_ONLY negative test | Caller migration, run admission evidence |
| `strattester/research/execution.py:{simulate_trade,simulate_scale_trade}` | MOVE candidate to Terminan | NOT MOVED | OHLC bar fill/SL/TP parity, no-lookahead, policy/Math boundary |
| `strattester/research/statistics.py:evaluate_trades` | MOVE candidate to Math | NOT MOVED | Numeric finite/precision/CI parity |
| `strattester/marketdata/bybit_client.py:BybitClient`, `marketdata/sync_engine.py:SyncEngine` | MERGE candidate into Grid | Grid PR #292 only moved unique public bounded kline *dataset route selection* | Grid snapshot v1.1 covers 1m historical_aggregate, NOT all candles, mark, OI etc; no switch safe |
| `strattester/persistence/result_store.py:ResultStore` | KEEP until owner decision | Unmodified | Fenced readback/experiment ledger and rollback |
| Strattester independent Windows service/repo | DELETE/ARCHIVE candidate only | No deletion and no branch cleanup | #114 import manifest, #115 archive proof, #116 real physical E2E, full-history security |

### Cross-workstream coordination

- Source owner: Strattester #86; actual target work: Terminan PR #88 + canonical Terminan PR #87.
- `unified-system#114`: register old import paths, canonical `terminan.strategies`, `terminan.contracts` (hypothesis-only) and pending Grid/Math consumers.
- `unified-system#115`: no retirement before every active source consumer and recovery/secret scan passes.
- `unified-system#116`: CI unit results alone cannot claim real Bybit, Windows, installer, restart or recovery acceptance.
- **Diff observation:** integrated PR #88 touched 4 files, +280/-1 vs Terminan main; internal duplicate implementation removed from its prior candidate; net system LOC reduction **not yet demonstrated**.
- **CI:** previous PR #87 and PR #88 isolated heads PASS; stage3 combined HEAD `603ae1d9a05087a2640564885b0b47388980e9ff` queued at last check. No exact-head PASS assumed.

**NO_GO** — source code and historical data remain intact. Never mass-delete branches or archive without independent sign-off and explicit user permission.
