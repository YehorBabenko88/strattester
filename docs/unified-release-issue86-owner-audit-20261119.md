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

## Stage 4: critical Terminan PR #87/#88 final-tree reconciliation

- Terminan canonical owner PR #87 HEAD: `c19085cee84539855c51d492772bf7e0124e46dc`.
- Existing Strattester-side Terminan PR #88 was reconciled **without a new branch or registry**. New exact HEAD: `66217c11f6fb046deba91d10dacaf1871e8b6ee7`.
- PR #88 tree now matches PR #87 canonical tree SHA `c1e7c6db648787c378bbcc40e68dd3424478528f`; `terminan/contracts.py` blob `1cd11250594faa5d80d1c8ee5f9244afa9097bba` and `tests/test_contracts.py` blob `9eb61b86c6780b69c16bd35d9cbf05103f94b277` match the owner source exactly.
- Neither tree contains `terminan/strategies.py` or `tests/test_strategies.py`. Exactly one strategy registry class remains within `terminan/contracts.py` (owner tree); the obsolete `from .strategies` reference introduced in older PR #88 was eliminated from the final tree.
- Original `strattester/strategies/registry.py` and `strattester/strategies/base.py` are still present in Strattester, as external callsite migration and rollback proof remain incomplete. No user data or original Git history was modified.
- PR #88 new HEAD has different commit ancestry from #87, but same source tree. **Never merge both independently**; owner selects canonical merge route and review. Stage4 exact-head CI queued at the first check; independently green *older* heads do not establish a PASS.
- Source imports/entrypoints in other repositories, semantic execution parity, real source Grid/Math/Terminan E2E, Windows installer/rollback, all Git refs secret scan remain blockers under #114/#115/#116.

## Stage 5: fail-closed elimination of one direct Bybit connection entrypoint

**Actual code changes on this Strattester Draft PR #87:** 
- `strattester/marketdata/download_smoke.py:run_download_smoke` no longer imports/instantiates `BybitClient` when caller omits a source. It returns `GRID_SOURCE_REQUIRED` without opening network or touching disk; a non-conforming supplied source returns `GRID_KLINES_INTERFACE_REQUIRED`. Existing explicit injected-client path remains temporarily to preserve test compatibility while Grid's authenticated read contract is defined.
- `strattester/marketdata/download_smoke_cli.py:main` no longer invokes `run_download_smoke` and fails closed with exit 2 / `GRID_SOURCE_REQUIRED`. This prevents an unreviewed direct exchange connection or independent local market DB from this standalone executable.
- `tests/marketdata/test_download_smoke.py` now exercises no implicit Bybit instantiation, no directory/database side effects and a denied standalone CLI. **Tests added but exact-head CI qualification must be observed**.

**No Grid API was fabricated or authenticated:** the existing Grid `fetch_kline_page` API is a different interface and a full read-only contract for every Strattester dataset is still unapproved. This change intentionally disables the unsafe entrypoint until the source owner supplies a versioned interface. This is not a migration of `SyncEngine`, `ResearchRunner`, `UniverseSynchronizer` or raw store writes; those remain outstanding and must not be falsely counted as migrated.

**Architecture decisions:** Unified provisions PostgreSQL and manages SSH/LAN orchestration; Grid alone connects Bybit and controls canonical market schema/writes; Math alone computes domain statistics; Terminan alone runs strategies. Strattester is transitional and must not be an installed service after E2E and data-backfill verification. Unique historical user SQLite, sharded files and persisted experiment results are preserved. No git history deletion, service restart or native/physical access performed.

**KEEP/MOVE/MERGE/DELETE:** KEEP original data and readback; MOVE request/REST ownership to Grid; MERGE duplicated legacy smoke into Grid's single collector; DELETE candidates `download_smoke_cli.py`, `bybit_client.py`, `sync_engine.py` only once every caller and rollback gate passes. Real removed source: implicit `BybitClient()` connection invocation; no removed tracked files.

**Blockers:** #114 complete import and entrypoint graph; #115 retirement; #116 real provider+Windows E2E; #112 all-refs secrets; Grid dataset-specific read API authn/authz/provenance; Terminan simulation and Math calculations; Unified PG and distributed SSH HA. Release **NO_GO**, main merge **NO**.

## Stage 6: Meta Analyse versus Strattester — cross-repository overlap / retirement evidence

Scope is **read-only symbol comparison**, not complete audit of all 784 Meta PR #81 blobs or all non-main branches. Pinned Meta PR #81 `b49505da42a274f7232fabe5d847c91f7218a0ce`, Strattester research #83 `d6293f75db7fcc8eed0900521a1ba6bd46b3468e`, Math #121 `013b0e84d8265aa9af8e072f380ca481c16869a3`. These are audited snapshots, not immutable latest pointers.

| Meta exact symbol / source | Strattester related implementation | USED/UNUSED claim | Destination owner & action | Equivalence / deletion gate |
|---|---|---|---|---|
| `src/meta_analyse/core.py:Minute.poc`, `footprint.py:Footprint.poc` | `strattester/research/volume_profile.py:_profile,trade_profile,proxy_profile` | USED status **UNKNOWN** until call graph; two Meta profiles known in candidate | **Math MOVE / MERGE** POC; Terminan consumes result | Meta Minute close-nearest tie vs Footprint low-price tie; Strattester POC low-price tie and **70% value area** (VAH/VAL) additional unique outputs. Math #121 current API must explicitly retain all modes and values before removing any source |
| `src/meta_analyse/orderflow_metrics.py:calculate` | `strattester/research/orderflow.py:cumulative_delta,aggression_decay,cvd_divergence` | UNKNOWN | **Math MOVE / MERGE** numeric CVD/delta; Terminan owns signals | Meta Decimal buy/sell/**unknown** side and imbalance nullable; Strattester float per-row volumes and cumulative sequence. Different precision/unknown semantics and row granularity, not equivalent |
| `src/meta_analyse/tape_velocity.py:TapeVelocity.add` | `strattester/research/orderflow.py:aggression_decay`; `microstructure.py:detect_absorption_proxy` | UNKNOWN | **Math MOVE** tape speed/notional/near-level rolling windows; Terminan signal presentation | Distinct time window and continuity reset; not replacement by aggression_decay |
| `src/meta_analyse/wall_tracker.py:WallTracker.observe` | `strattester/research/microstructure.py:detect_absorption_proxy` | UNKNOWN | **Math MOVE** orderbook wall measurement; Terminan alerts | Wall disappearance is explicitly **unverified cancellation or execution**, not proof of spoofing; preserve reset-on-invalid and monotone-clock behavior |
| `src/meta_analyse/level_sync.py:LevelSync.replace,crossed`, `level_publish.py:publication_decision` | `strattester/research/levels.py:completed_period_levels` | UNKNOWN | **Terminan MOVE** level controls and ownership; **Math MOVE** period-level computation | Stable Meta signature `meta_analyse:` and ownership filtering; preserve existing user levels, instrument proof and fail-closed non-destructive update. Numeric period-level detection separate from UI mutation |
| `src/meta_analyse/desktop.py:Window`, `metascalp_locator.py:find_metascalp` | Strattester no equivalent final UI (service/telegram tools separate) | UNKNOWN | **Terminan MOVE** unique MetaScalp/window behavior, retire Qt executable only after feature parity | Preserve watchlist, FlowTable sorting, tape/chart/flow history, settings; do not start second UI |
| `src/meta_analyse/analysis_session.py:AnalysisSession.start`, `market_collector.py:MarketCollector` | `strattester/marketdata/sync_engine.py:SyncEngine`, `universe_sync.py:UniverseSynchronizer` | UNKNOWN | **Grid MOVE / MERGE** source acquisition; **Unified** owns lifecycle | Two independent Bybit paths prohibited; Grid endpoint must provide raw/provenance/coverage/instrument contract before consumer cutover |
| `src/meta_analyse/flow_history_storage.py:read_flow_history`, `orderflow_archive_reader.py:read_orderflow_trades` | `strattester/marketdata/sqlite_store.py`, `sharded_store.py` | UNKNOWN | **Grid MOVE** history read APIs / one market writer | Meta #81 internal SQL SELECT duplicate partially merged. Preserve Decimal values, UTC epoch ms, read-only transactional semantics, existing stored trade ids |
| `src/meta_analyse/history.py:validate_fixed_interval,yearly_from_daily` | `strattester/marketdata/coverage.py:Coverage`, `sync_engine.py:SyncEngine._ranges` | UNKNOWN | **Grid MOVE / MERGE** historical gap integrity; **Math** calendar aggregations if domain transform | Different UTC/period semantics: Meta refuses missing days and synthetic yearly bars; Grid must not label incomplete history complete |
| `src/meta_analyse/orderflow_metrics.py:calculate` and `core.py:PaperEngine` | `strattester/research/execution.py:simulate_trade,simulate_scale_trade` | UNKNOWN | Calculation to **Math**, paper execution to **Terminan** | Keep separate source provenance/fees/slippage, same-bar conservative SL-first, replay seed and OOS tests |

**Cross-domain safety finding:** Strattester 70% VAH/VAL and causal cutoff `known_at`, its `aggression_decay`/CVD-divergence, Meta rolling tape continuity and wall disappearance evidence are *not demonstrated* in Math `market_compute_api.compute_batch` v1. Do not mark these UNUSED or DELETE merely because initial POC/Delta migration exists. A genuine capability inventory needs actual entrypoint/import graph #114 plus owner ACK and matching-input parity.

**Release snapshot:** Strattester Draft #87 includes no Meta runtime consumer switch and no Meta source deletion. Existing old data, settings and SHA-pinned tests retained. CI from previous Strattester HEAD `f32487c397ee2f29f30800b97ff0d8a19a8c2ed6` **FAIL** due to literal escaped newlines in `download_smoke.py` (2 test failures, other tests mostly passed). Corrected in same PR at `5ee403537e70a7b1ae9614c121612af39bba4c41`; exact-head CI must be verified independently. No physical machine/provider/restart/rollback tests.

**Archive decision:** Meta Analyse and Strattester are both **NOT_READY** for archive/delete. Required: last-consumer graph, canonical Grid full dataset and Math numerical APIs, Terminan paper/UI parity, Unified owner-only DB/orchestrator, real-source E2E #116, historical secret scan #112, full data/settings export and restore, explicit user approval for named repositories.

## Stage 10: offline installer entrypoint

- KEEP the local preflight, worker smoke, and historical data/results. The downloaded-history CLI remains a guarded compatibility entrypoint for direct callers.
- MOVE market-source qualification to Grid and service deployment to Unified. The Strattester installer no longer invokes its direct Bybit connectivity probe or disabled downloader, which always returned exit 2.
- MERGE acceptance through the owner-published contracts. Terminan's current bounded paper replay does not accept the Strattester multi-dataset strategy context and checkpoint, so `ResearchRunner` still refuses execution. The regression compares a SHA-256 digest of the SQLite logical dump around repeated refusals.
- DELETE the two installer invocations. Keep legacy files pending external consumer verification and rollback.
