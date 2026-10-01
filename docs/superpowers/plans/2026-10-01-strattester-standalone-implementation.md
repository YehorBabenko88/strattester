# Strattester Standalone Foundation and Remote Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-installing, resilient Windows Strattester node that safely reuses or creates Bybit data, runs versioned strategies as services, supports Telegram operations, and can later be remotely updated from GitHub with rollback.

**Architecture:** Keep high-volume market data in local SQLite and isolate runtime/control state behind a state-store interface that can later use PostgreSQL. A lightweight controller owns Telegram and deployment control while a worker owns synchronization/backtests; GitHub releases/commits are staged, tested, atomically activated, and rolled back on failed health checks. Tailscale is optional for private diagnostics/administration and is never required for normal service operation.

**Tech Stack:** Python 3.11+, PowerShell 5.1+, SQLite, requests, psutil, pytest, NSSM on Windows, optional PostgreSQL, optional Tailscale.

**Spec:** `docs/superpowers/specs/2026-10-01-strattester-architecture-design.md`

## Global Constraints

- Windows standalone mode must work without PostgreSQL.
- Large market-data SQLite databases must remain on local disks, never as live writable databases over SMB.
- Existing databases are discovered and inspected read-only before adoption or migration.
- Synchronization is idempotent and coverage-based.
- One failed symbol/dataset must not terminate the entire service.
- Strategies are versioned plugins and must not dictate the raw market-data schema.
- Controller owns Telegram updates; worker performs heavy synchronization/backtests.
- Secrets stay local and are never committed.
- Destructive operations require explicit confirmation.
- Ordinary CI must not require live Bybit connectivity.
- Remote deployment must fail closed, preserve data, health-check the candidate, and support rollback.
- Tailscale is optional; no public inbound port is required.

## Review Focus

- A 40-60 GB legacy SQLite database is discovered without accidentally creating a new empty database and is never modified during discovery.
- Interrupted/overlapping Bybit synchronization resumes without duplicate candles or deleting valid historical ranges.
- A bad GitHub update cannot replace the known-good running version; failed health checks roll back automatically.
- Worker crash/reboot preserves durable job state and does not falsely mark work complete.
- Low RAM/disk or a locked database pauses/retries work rather than causing an uncontrolled crash.

---

### Task 1: Repository foundation, configuration, and doctor

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `strattester/__init__.py`
- Create: `strattester/config.py`
- Create: `strattester/doctor.py`
- Create: `tests/test_config.py`
- Create: `tests/test_doctor.py`

**Interfaces:**
- Produces: `AppConfig.load(root: Path) -> AppConfig`
- Produces: `run_doctor(config: AppConfig) -> DoctorReport`

- [ ] **Step 1: Write failing configuration tests**
  - Test defaults use local `data/`, `results/`, `logs/`, `state/`.
  - Test environment/local config overrides do not expose Telegram secrets in repr/log output.

- [ ] **Step 2: Run tests and verify failure**
  - Run: `python -m pytest tests/test_config.py -v`
  - Expected: FAIL because package/config does not exist.

- [ ] **Step 3: Implement minimal configuration layer**
  - Implement immutable/path-normalized `AppConfig`, local secret loading, directory creation separated from config parsing.

- [ ] **Step 4: Write and implement doctor tests**
  - Exercise writable paths, Python version, free disk, DB path existence without creating a missing DB, and optional PostgreSQL/Tailscale status.

- [ ] **Step 5: Verify**
  - Run: `python -m pytest tests/test_config.py tests/test_doctor.py -v`
  - Expected: PASS.

- [ ] **Step 6: Commit**
  - `git commit -m "feat: add strattester foundation and doctor"`

### Task 2: Legacy database discovery and safe adoption

**Files:**
- Create: `strattester/marketdata/discovery.py`
- Create: `strattester/marketdata/integrity.py`
- Create: `tests/marketdata/test_discovery.py`
- Create: `tests/marketdata/test_integrity.py`

**Interfaces:**
- Consumes: `AppConfig`
- Produces: `discover_databases(config: AppConfig, extra_paths: Sequence[Path]) -> list[DatabaseCandidate]`
- Produces: `inspect_database(path: Path) -> DatabaseInspection`
- Produces: `adopt_database(candidate: DatabaseCandidate, destination: Path) -> AdoptionResult`

- [ ] **Step 1: Write failing discovery tests**
  - Missing candidate is not created.
  - Valid legacy DB is opened with SQLite URI `mode=ro`.
  - Candidates are ranked by recognized schema, integrity, coverage/freshness, then size.
  - A fake large/invalid file is rejected.

- [ ] **Step 2: Verify failure**
  - Run: `python -m pytest tests/marketdata/test_discovery.py -v`

- [ ] **Step 3: Implement discovery/inspection**
  - Bounded candidate search only; no unrestricted full-drive recursion by default.
  - Read-only inspection and `PRAGMA quick_check` support.

- [ ] **Step 4: Write adoption safety tests**
  - Adoption never overwrites an unrelated existing destination.
  - Existing source remains intact until explicit adoption completes.
  - Missing source fails without creating an empty SQLite file.

- [ ] **Step 5: Implement adoption and verify**
  - Run: `python -m pytest tests/marketdata/test_discovery.py tests/marketdata/test_integrity.py -v`
  - Expected: PASS.

- [ ] **Step 6: Commit**
  - `git commit -m "feat: discover and safely adopt legacy databases"`

### Task 3: Versioned market-data schema and coverage index

**Files:**
- Create: `strattester/marketdata/schema.py`
- Create: `strattester/marketdata/sqlite_store.py`
- Create: `strattester/marketdata/coverage.py`
- Create: `strattester/marketdata/migrations/__init__.py`
- Create: `tests/marketdata/test_store.py`
- Create: `tests/marketdata/test_coverage.py`

**Interfaces:**
- Produces: `SQLiteMarketStore.open(path: Path) -> SQLiteMarketStore`
- Produces: `upsert_candles(records: Iterable[Candle]) -> WriteStats`
- Produces: `coverage(symbol: str, dataset: str, timeframe: str) -> Coverage`
- Produces: `find_gaps(...) -> list[TimeRange]`

- [ ] **Step 1: Write failing idempotency/conflict tests**
  - Duplicate identical candle produces no duplicate.
  - Superior complete record may repair incomplete record.
  - Malformed regression is rejected and logged.
  - Interrupted bounded transaction leaves no half-batch.

- [ ] **Step 2: Verify failure**
  - Run: `python -m pytest tests/marketdata/test_store.py -v`

- [ ] **Step 3: Implement schema/store**
  - Unique key `(symbol,timeframe,open_time)` for candles; equivalent explicit keys for later datasets.
  - Schema-version table and bounded transactions.

- [ ] **Step 4: Implement coverage tests and coverage index**
  - Pin earliest/latest timestamps and intentional internal gap detection.

- [ ] **Step 5: Verify**
  - Run: `python -m pytest tests/marketdata/test_store.py tests/marketdata/test_coverage.py -v`

- [ ] **Step 6: Commit**
  - `git commit -m "feat: add idempotent market data store and coverage"`

### Task 4: Resilient Bybit synchronization

**Files:**
- Create: `strattester/marketdata/bybit_client.py`
- Create: `strattester/marketdata/sync_engine.py`
- Create: `tests/marketdata/test_bybit_client.py`
- Create: `tests/marketdata/test_sync_engine.py`

**Interfaces:**
- Consumes: `SQLiteMarketStore`, coverage interfaces.
- Produces: `BybitClient.fetch_*()`
- Produces: `SyncEngine.sync_requirement(requirement: DataRequirement) -> SyncResult`

- [ ] **Step 1: Write failing HTTP/retry tests**
  - 429 and temporary 5xx become retryable with bounded exponential backoff.
  - Generic access 403 becomes explicit degraded/non-looping error.
  - Invalid/incomplete responses do not delete existing history.

- [ ] **Step 2: Verify failure**
  - Run: `python -m pytest tests/marketdata/test_bybit_client.py -v`

- [ ] **Step 3: Implement client**
  - Injectable HTTP transport/clock for deterministic tests.

- [ ] **Step 4: Write synchronization tests**
  - Empty DB downloads required range.
  - Existing DB appends only missing/new closed data.
  - Internal gaps are repaired.
  - Overlap is harmless.
  - Interrupted sync resumes.
  - Database lock transitions to retryable state.

- [ ] **Step 5: Implement state machine and verify**
  - States: UNKNOWN/CHECKING/PARTIAL/SYNCING/VALIDATING/READY/DEGRADED/RETRYABLE/REPAIR_REQUIRED.
  - Run: `python -m pytest tests/marketdata -v`
  - Expected: PASS.

- [ ] **Step 6: Commit**
  - `git commit -m "feat: add resilient coverage based bybit sync"`

### Task 5: Strategy plugin registry and versioned results identity

**Files:**
- Create: `strattester/strategies/base.py`
- Create: `strattester/strategies/registry.py`
- Create: `strattester/strategies/builtin/__init__.py`
- Create: `strattester/engine/executor.py`
- Create: `tests/strategies/test_registry.py`
- Create: `tests/engine/test_executor.py`

**Interfaces:**
- Produces: `StrategyDefinition`, `DataRequirement`
- Produces: `StrategyRegistry.discover() -> list[StrategyDefinition]`
- Produces: `strategy_fingerprint(definition) -> str`
- Produces: `execute_strategy(job, store, checkpoint) -> StrategyResult`

- [ ] **Step 1: Write failing registry tests**
  - Duplicate strategy ID+version rejected.
  - Enable/disable does not delete historical results.
  - Changed strategy version/fingerprint creates distinct result identity.
  - Requirements block execution until coverage is ready.

- [ ] **Step 2: Verify failure**
  - Run: `python -m pytest tests/strategies -v`

- [ ] **Step 3: Implement plugin contracts/registry**

- [ ] **Step 4: Add executor streaming tests**
  - Ensure candle processing can iterate in chunks rather than `fetchall()`.
  - Ensure checkpoint carries strategy/config fingerprint.

- [ ] **Step 5: Implement executor and verify**
  - Run: `python -m pytest tests/strategies tests/engine/test_executor.py -v`

- [ ] **Step 6: Commit**
  - `git commit -m "feat: add versioned strategy plugin engine"`

### Task 6: Durable state store, jobs, checkpoints, and resource scheduler

**Files:**
- Create: `strattester/persistence/state_store.py`
- Create: `strattester/persistence/sqlite_state_store.py`
- Create: `strattester/engine/jobs.py`
- Create: `strattester/engine/checkpoints.py`
- Create: `strattester/engine/resource_manager.py`
- Create: `strattester/engine/scheduler.py`
- Create: `tests/engine/test_jobs.py`
- Create: `tests/engine/test_scheduler.py`
- Create: `tests/engine/test_resource_manager.py`

**Interfaces:**
- Produces: `StateStore` protocol.
- Produces: `SQLiteStateStore`.
- Produces: durable `Job` state machine.
- Produces: `ResourceSnapshot`, `SchedulingDecision`.

- [ ] **Step 1: Write failing durable job/recovery tests**
  - RUNNING job with stale lease returns to RETRYABLE.
  - COMPLETE cannot be inferred from worker disappearance.
  - Incompatible config/strategy fingerprint invalidates resume safely.

- [ ] **Step 2: Implement state/job/checkpoint layer**

- [ ] **Step 3: Write resource tests**
  - <75% RAM normal; 75-85% throttles; 85-92% pauses heavy issuance; >92% requests controlled checkpoint/release.
  - Low absolute free RAM and low disk override percentage-only decisions.

- [ ] **Step 4: Implement scheduler/resource manager**

- [ ] **Step 5: Verify**
  - Run: `python -m pytest tests/engine -v`

- [ ] **Step 6: Commit**
  - `git commit -m "feat: add durable jobs and resource aware scheduler"`

### Task 7: Worker runtime, structured logging, and graceful lifecycle

**Files:**
- Create: `strattester/runtime/logging.py`
- Create: `strattester/runtime/worker.py`
- Create: `strattester/runtime/lifecycle.py`
- Create: `tests/runtime/test_worker.py`
- Create: `tests/runtime/test_logging.py`

**Interfaces:**
- Consumes: sync engine, scheduler, state store, strategy executor.
- Produces: `WorkerRuntime.run() -> int`
- Produces: graceful stop/drain/checkpoint behavior.

- [ ] **Step 1: Write worker lifecycle tests**
  - SIG/stop request checkpoints before exit where safe.
  - One symbol failure is recorded and scheduler continues.
  - Logs contain component/job/symbol/strategy identifiers.
  - Rotation prevents unbounded log growth.

- [ ] **Step 2: Implement worker/logging**

- [ ] **Step 3: Verify**
  - Run: `python -m pytest tests/runtime -v`

- [ ] **Step 4: Commit**
  - `git commit -m "feat: add resilient worker runtime and logging"`

### Task 8: Telegram controller and safe operations

**Files:**
- Create: `strattester/telegram/controller.py`
- Create: `strattester/telegram/commands.py`
- Create: `tests/telegram/test_controller.py`
- Create: `tests/telegram/test_commands.py`

**Interfaces:**
- Produces: controller commands START/STOP/RESTART/DRAIN/STATUS/RAM/SYNC/REPAIR/STRATEGIES.
- Produces: confirmation nonce flow for destructive actions.

- [ ] **Step 1: Write authorization/command tests**
  - Unknown chat/user ignored.
  - Controller remains usable while worker is stopped.
  - Destructive command requires expiring confirmation.
  - STOP changes desired state so watchdog does not immediately restart worker.

- [ ] **Step 2: Implement controller/commands**

- [ ] **Step 3: Verify**
  - Run: `python -m pytest tests/telegram -v`

- [ ] **Step 4: Commit**
  - `git commit -m "feat: add telegram service controller"`

### Task 9: One-command Windows installation and NSSM services

**Files:**
- Create: `install.ps1`
- Create: `service/install_windows.ps1`
- Create: `service/uninstall_windows.ps1`
- Create: `service/strattester-worker.cmd`
- Create: `service/strattester-controller.cmd`
- Create: `tests/install/test_install_contract.py`

**Interfaces:**
- Produces Windows services `StrattesterController`, `StrattesterWorker`.

- [ ] **Step 1: Write installer contract tests**
  - Re-running install is idempotent.
  - Existing data directory is preserved.
  - Uninstall defaults to preserving data/results.
  - Missing Python/NSSM has deterministic bootstrap path.
  - Secrets are written only to local protected/configured storage.

- [ ] **Step 2: Implement bootstrap/install scripts**
  - Use pinned download URLs/checksums for externally downloaded bootstrap binaries where practical.
  - NSSM: automatic start, non-zero restart, graceful stop, rotating wrapper logs.

- [ ] **Step 3: Add dry-run mode**
  - `install.ps1 -DryRun` reports actions without service/data mutation.

- [ ] **Step 4: Verify Python-side installer contracts**
  - Run: `python -m pytest tests/install -v`

- [ ] **Step 5: Commit**
  - `git commit -m "feat: add one command windows service installer"`

### Task 10: Safe remote GitHub deployment with automatic rollback

**Files:**
- Create: `strattester/deploy/updater.py`
- Create: `strattester/deploy/releases.py`
- Create: `strattester/deploy/healthcheck.py`
- Create: `service/update.ps1`
- Create: `tests/deploy/test_updater.py`
- Create: `tests/deploy/test_healthcheck.py`
- Create: `.github/workflows/tests.yml`
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Produces: `UpdateManager.check() -> UpdateCandidate | None`
- Produces: `UpdateManager.stage(candidate) -> StagedRelease`
- Produces: `UpdateManager.activate(staged) -> ActivationResult`
- Produces: `UpdateManager.rollback() -> RollbackResult`

- [ ] **Step 1: Write update safety tests**
  - Uncommitted/local data directories are outside release tree and never replaced.
  - Candidate must identify immutable commit/release.
  - Failed download/checksum/test does not stop known-good worker.
  - Failed post-activation health check restores previous release.
  - Interrupted activation resolves to either previous or new complete release, never a half-updated directory.

- [ ] **Step 2: Implement versioned release layout**
  - `releases/<commit>/` plus atomic `current` pointer/junction.
  - Keep at least previous known-good release.
  - Data/state/results/logs live outside release directory.

- [ ] **Step 3: Implement staged validation**
  - Create/use release venv, install pinned dependencies, run migration preflight and selected tests/doctor before activation.

- [ ] **Step 4: Implement activation/rollback**
  - DRAIN worker, activate release, restart, health-check; rollback automatically on failure.

- [ ] **Step 5: Add GitHub CI/release workflows**
  - Ordinary tests mocked/offline.
  - Release artifact tied to immutable commit SHA.

- [ ] **Step 6: Verify**
  - Run: `python -m pytest tests/deploy -v`
  - Expected: PASS.

- [ ] **Step 7: Commit**
  - `git commit -m "feat: add safe remote github deployment and rollback"`

### Task 11: Optional Tailscale administration

**Files:**
- Create: `strattester/remote/tailscale.py`
- Create: `docs/remote-administration.md`
- Create: `tests/remote/test_tailscale.py`

**Interfaces:**
- Produces: `detect_tailscale() -> TailscaleStatus`
- No core runtime dependency on Tailscale.

- [ ] **Step 1: Write optionality tests**
  - Missing Tailscale does not degrade worker/controller health.
  - Installed Tailscale status is reported by doctor/status without exposing auth keys.

- [ ] **Step 2: Implement detection and documentation**
  - Document private RDP/SSH/diagnostic use over tailnet.
  - Do not open a public service port.
  - Do not auto-enroll a machine using a committed/shared auth key.

- [ ] **Step 3: Verify**
  - Run: `python -m pytest tests/remote -v`

- [ ] **Step 4: Commit**
  - `git commit -m "feat: add optional tailscale administration support"`

### Task 12: Optional PostgreSQL state backend

**Files:**
- Create: `strattester/persistence/postgres_state_store.py`
- Create: `strattester/persistence/migrate_state.py`
- Create: `tests/persistence/test_state_contract.py`
- Create: `tests/persistence/test_postgres_optional.py`

**Interfaces:**
- Implements the same `StateStore` protocol as local SQLite state.

- [ ] **Step 1: Write shared backend contract tests**
  - Job transitions/checkpoints produce equivalent behavior on local and PostgreSQL implementations.

- [ ] **Step 2: Implement optional PostgreSQL adapter**
  - Import dependency lazily; standalone install remains functional without PostgreSQL driver/server.

- [ ] **Step 3: Implement state migration utility**
  - Copy/verify state without touching market-data SQLite.

- [ ] **Step 4: Verify**
  - Run local contract tests always; PostgreSQL integration tests only when test DSN is configured.

- [ ] **Step 5: Commit**
  - `git commit -m "feat: add optional postgres state backend"`

### Task 13: Port existing strategy semantics and regression fixtures

**Files:**
- Create: `strattester/strategies/builtin/legacy_grid.py`
- Create: `tests/fixtures/legacy_market_sample.sqlite3` or generated fixture builder
- Create: `tests/regression/test_legacy_grid.py`

**Interfaces:**
- Consumes strategy plugin/executor contracts.
- Produces versioned built-in legacy strategy suite preserving agreed entry/exit semantics.

- [ ] **Step 1: Build compact deterministic fixture**
  - Cover equality touch, strict break, HIGH/LOW direction, SL-first ambiguity, no same-minute exit after new entry, fees, stopped-level reuse.

- [ ] **Step 2: Write failing regression assertions**
  - Pin exact trade counts/entry/exit/PnL for fixture.

- [ ] **Step 3: Port existing semantics into plugin**

- [ ] **Step 4: Verify**
  - Run: `python -m pytest tests/regression -v`

- [ ] **Step 5: Commit**
  - `git commit -m "feat: port legacy strategy semantics"`

### Task 14: End-to-end Windows acceptance and documentation

**Files:**
- Create: `docs/install-windows.md`
- Create: `docs/recovery.md`
- Create: `docs/strategy-development.md`
- Create: `docs/database-migration.md`
- Create: `scripts/windows-smoke.ps1`

**Interfaces:**
- Validates the complete standalone product.

- [ ] **Step 1: Add scripted acceptance sequence**
  - Fresh install.
  - Adopt pre-existing DB.
  - Start services.
  - Sync bounded test symbol/range.
  - Run one strategy.
  - Stop/start via controller.
  - Kill worker unexpectedly and verify recovery.
  - Simulate bad update and verify rollback.
  - Uninstall and verify data preserved.

- [ ] **Step 2: Run complete offline suite**
  - Run: `python -m pytest -v`
  - Expected: all offline tests PASS.

- [ ] **Step 3: Run Windows smoke on a real Windows node**
  - Expected: all acceptance stages PASS; retain logs as evidence.

- [ ] **Step 4: Document operator workflows**
  - Include remote update from GitHub, rollback, optional Tailscale access, DB migration, adding a strategy.

- [ ] **Step 5: Commit**
  - `git commit -m "docs: add windows operations and acceptance workflow"`

## Self-Review

- Spec coverage: standalone bootstrap, DB discovery/adoption, idempotent sync, strategy plugins, durable jobs, RAM-aware scheduling, Telegram, NSSM, logging, PostgreSQL option, security, tests, and future cluster-compatible boundaries are represented.
- New requirement coverage: remote GitHub deployment is isolated from data, staged before activation, health-checked, and rollback-capable; Tailscale is optional.
- Type consistency: market data, strategy requirements, state store, jobs, and deployment interfaces have single owners and are consumed only after their defining tasks.
- Review-focus failures are explicitly exercised in Tasks 2-4, 6, 9-10.
- Cluster master/node implementation remains intentionally outside this first standalone plan; interfaces are kept compatible with the approved architecture.
