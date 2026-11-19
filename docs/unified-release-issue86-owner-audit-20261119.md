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
