# Strattester Architecture Design

Date: 2026-10-01
Status: Approved design draft
Repository: YehorBabenko88/strattester

## 1. Purpose

Strattester is intended to be a self-configuring, resilient Bybit strategy-testing platform for Windows computers with minimal user intervention.

A fresh machine should be able to clone the repository, run one installer, and obtain a working Windows service that:

- detects or creates the required runtime environment;
- detects an existing local Bybit market-data database when available;
- validates and safely reuses existing data rather than redownloading everything;
- downloads and repairs missing Bybit history when needed;
- keeps data synchronized without duplicate rows or destructive conflicts;
- runs strategy backtests in parallel while respecting CPU and RAM limits;
- persists state and resumes after crashes, forced process termination, or reboot;
- is controlled through Telegram;
- logs all important operations and failures;
- allows strategies to be added, removed, enabled, disabled, and versioned without redesigning the market-data schema;
- can run standalone on one PC now and evolve into a multi-PC cluster later.

## 2. Architectural Decision

Use a hybrid storage architecture.

### 2.1 Local SQLite market-data archive

Large historical time-series data remain local to each computer in SQLite or equivalent local files.

Primary use:

- 1m candles;
- mark/index/premium history;
- funding history;
- open interest;
- long/short ratios;
- public trade aggregates;
- other high-volume historical market datasets.

SQLite must always be used from a local disk, never as a live database over SMB.

### 2.2 Optional PostgreSQL control/state backend

PostgreSQL is not mandatory for initial standalone operation.

When available, it is used for:

- job state;
- node state;
- strategy definitions and versions;
- run metadata;
- checkpoints;
- result metadata;
- ML/feature metadata;
- cluster scheduling and coordination.

A standalone node must still work when PostgreSQL is absent by using a local state backend.

This keeps installation simple while preserving a clean upgrade path to a five-PC cluster.

## 3. High-Level Components

```text
strattester/
  bootstrap/
      install.ps1
      doctor.py
      migrate_legacy.py

  app/
      main.py
      config.py
      service.py

  marketdata/
      discovery.py
      bybit_client.py
      sync_engine.py
      coverage.py
      integrity.py
      sqlite_store.py
      migrations/

  strategies/
      base.py
      registry.py
      builtin/
      manifests/

  engine/
      scheduler.py
      worker.py
      executor.py
      checkpoints.py
      resource_manager.py

  persistence/
      state_store.py
      sqlite_state_store.py
      postgres_store.py
      schema/

  telegram/
      controller.py
      commands.py

  service/
      install_windows.ps1
      uninstall_windows.ps1
      nssm/

  tests/
  data/
  results/
  logs/
```

## 4. Installation and Bootstrap

The target user workflow is:

```powershell
git clone https://github.com/YehorBabenko88/strattester.git
cd strattester
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer should perform the following automatically where practical:

1. validate supported Windows version;
2. locate a usable Python runtime or install one;
3. create a virtual environment;
4. install pinned dependencies;
5. create configuration directories;
6. locate possible legacy Bybit databases;
7. select and validate a reusable database;
8. migrate schemas non-destructively;
9. initialize the state backend;
10. configure logging;
11. install NSSM if needed;
12. install the controller and worker services;
13. configure restart/recovery policy;
14. perform health checks;
15. start services.

Telegram credentials are expected to be one of the few user-supplied values.

Secrets must not be committed to GitHub.

## 5. Existing Database Discovery

The application must not assume a fixed installation directory.

Discovery should inspect:

- configured paths;
- the current application data directory;
- known legacy project directories;
- user-selected paths;
- optionally a bounded local drive search for known database filenames.

Candidate databases are ranked using:

- successful open in read-only mode;
- schema recognition;
- file size;
- data coverage;
- freshness;
- integrity status.

No candidate is modified during discovery.

A database selected for adoption must first be backed up or registered as a legacy source before schema migration.

## 6. Data Synchronization Model

The synchronization engine is coverage-based rather than "download all again".

For every relevant tuple:

```text
(symbol, dataset, timeframe)
```

the system tracks:

- earliest stored timestamp;
- latest stored timestamp;
- known gaps;
- validation state;
- last successful sync;
- last attempted sync;
- schema/data version.

Startup flow:

```text
DISCOVER
  -> IDENTIFY SCHEMA
  -> INTEGRITY CHECK
  -> DISCOVER COVERAGE
  -> COMPARE TO SOURCE
  -> REPAIR GAPS
  -> APPEND NEW CLOSED DATA
  -> VALIDATE
  -> READY
```

## 7. Data Conflict and Idempotency Rules

Synchronization must be idempotent.

Repeated downloads must not create duplicate rows.

Typical candle uniqueness:

```text
(symbol, timeframe, open_time)
```

Equivalent unique keys must exist for other datasets.

Incoming records are validated before write.

UPSERT behavior must:

- accept identical records harmlessly;
- repair incomplete rows when a superior validated record arrives;
- refuse obviously malformed regressions;
- keep diagnostic information when conflicting source values are detected;
- never delete large historical ranges merely because one API response is incomplete.

Network/API failure must not leave the database in a partially committed logical state.

Writes should use bounded transactions.

## 8. Synchronization State Machine

Each symbol/dataset may independently occupy states such as:

```text
UNKNOWN
CHECKING
PARTIAL
SYNCING
VALIDATING
READY
DEGRADED
RETRYABLE
REPAIR_REQUIRED
```

A failure for one symbol or dataset must not crash the entire long-running service.

Examples:

- HTTP 429 -> RETRYABLE with exponential backoff;
- temporary 5xx -> RETRYABLE;
- access restriction/403 -> explicit degraded/error state;
- database locked -> bounded retry with diagnostics;
- schema mismatch -> migration or REPAIR_REQUIRED;
- corrupt page/integrity failure -> quarantine/repair workflow.

The service persists state before sleeping or retrying.

## 9. Market-Data Safety

Rules:

- never run SQLite directly from a network share;
- avoid multiple uncontrolled writers to the same SQLite database;
- prefer one data-writer/coordinator process and reader workers;
- enable WAL only when local filesystem semantics are safe;
- use checkpoints intentionally;
- perform graceful close on service stop;
- retain a recoverable checkpoint;
- do not delete raw data before downstream results/features are durably accepted.

Large historical datasets may later support retention modes:

- FULL;
- COMPACT;
- MINIMAL.

Deletion must always happen after verified completion.

## 10. Strategy Architecture

Strategies are plugins, not hard-coded database schemas.

Each strategy declares metadata such as:

```python
class Strategy:
    id = "breakout_confluence"
    version = "2.1"

    requirements = {
        "candles": ["1m", "1h", "4h", "1d"],
        "public_trades": True,
        "open_interest": True,
        "funding": True,
    }
```

The registry is responsible for:

- discovery;
- validation;
- enable/disable state;
- version tracking;
- dependency checks;
- execution configuration.

Changing strategy code creates a new strategy version for result identity.

Old results must remain attributable to the exact version that produced them.

Removing a strategy from the active registry does not erase historical run results.

## 11. Strategy Requirements and Data Preparation

Before scheduling a strategy run, the engine resolves its declared datasets.

If data are missing:

1. market-data sync receives a prerequisite job;
2. the strategy job remains BLOCKED;
3. after validated coverage is available, it becomes READY;
4. the scheduler may execute it.

This prevents a strategy from silently running on incomplete history.

Derived features should be versioned separately from raw data.

## 12. Execution and Parallelism

Parallelism must be dynamic rather than fixed.

The resource manager measures:

- total RAM;
- available RAM;
- process working sets;
- CPU count;
- CPU utilization;
- disk free space;
- recent observed memory use by job type.

Suggested RAM behavior:

- below 75% used: normal scheduling;
- 75-85%: reduce issuance of new heavy jobs;
- 85-92%: pause new heavy jobs;
- above 92%: checkpoint and controlled release where safe.

The scheduler should learn approximate memory requirements from previous executions.

Work should prefer chunked/streamed iteration over full-table materialization.

## 13. Job Model

Durable jobs support states similar to:

```text
PENDING
BLOCKED
READY
LEASED
RUNNING
CHECKPOINTED
RETRYABLE
FAILED
COMPLETE
CANCELLED
```

Each job has:

- stable ID;
- job type;
- symbol;
- strategy/version where applicable;
- configuration hash;
- dependency list;
- attempt count;
- lease/ownership;
- checkpoint location;
- timestamps;
- error summary.

Reboot or worker loss must not silently mark a job complete.

## 14. Checkpoints and Resume

Checkpoints are durable and versioned.

On restart the service:

1. reads desired service state;
2. inspects incomplete jobs;
3. validates their checkpoints;
4. validates database prerequisites;
5. resumes safe work;
6. requeues invalid/stale leases;
7. never assumes a previous subprocess still owns a job.

Configuration incompatibility must invalidate or migrate checkpoints explicitly rather than quietly mixing settings.

## 15. Windows Services

The initial Windows implementation uses NSSM.

Logical services:

- `StrattesterController`
- `StrattesterWorker`

Controller:

- remains lightweight;
- owns Telegram updates;
- reports service/data status;
- controls desired worker state.

Worker:

- runs synchronization and strategy execution;
- may be restarted by NSSM after unexpected failure;
- must exit normally on deliberate stop.

NSSM desired behavior:

- automatic start after reboot;
- restart on unexpected non-zero exit;
- do not create an immediate restart loop after deliberate successful stop;
- stdout/stderr captured to rotating wrapper logs;
- graceful stop timeout before hard termination.

## 16. Telegram Control

Only the controller reads Telegram `getUpdates`.

Supported operations should include:

- START;
- STOP;
- RESTART;
- DRAIN;
- STATUS;
- RAM;
- SYNC;
- REPAIR;
- list strategies;
- enable strategy;
- disable strategy;
- current job/progress;
- recent errors.

Destructive actions require explicit confirmation with an expiring nonce.

Examples:

- remove service;
- purge results;
- reset state;
- delete market-data database.

Chat/user IDs must be allowlisted.

Telegram token remains local and secret.

## 17. Logging and Observability

Use structured logs in addition to human-readable text.

Minimum information:

- timestamp;
- component;
- level;
- node;
- job ID;
- symbol;
- strategy/version;
- event;
- retry count;
- elapsed time;
- error type.

Separate logical logs may include:

- application;
- controller;
- worker;
- synchronization;
- database/migration;
- strategy;
- service-wrapper.

Logs must rotate by size/time to prevent unbounded disk use.

Telegram should send important state transitions rather than spam every retry.

## 18. Health and Doctor Command

A `doctor` command should diagnose:

- Python/runtime;
- package versions;
- write permissions;
- database readability;
- database integrity;
- schema version;
- free disk;
- Telegram configuration;
- NSSM/service state;
- Bybit connectivity;
- state backend;
- PostgreSQL availability when configured.

It should return a machine-readable exit code and a concise repair recommendation.

## 19. PostgreSQL Integration

PostgreSQL remains optional for standalone mode.

A backend interface must hide whether state lives in:

- SQLite local state DB; or
- PostgreSQL.

This prevents the execution engine from depending directly on PostgreSQL.

PostgreSQL becomes preferred when cluster mode is enabled.

Automatic PostgreSQL installation should not be required in the first milestone.

## 20. Future Cluster Compatibility

The standalone architecture must not block future multi-PC operation.

Future cluster model:

- one master/coordinator;
- one NodeAgent per PC;
- local market-data database per node;
- durable task leases;
- heartbeat;
- authenticated LAN RPC;
- result shards returned to master;
- PostgreSQL as shared control plane if desired.

Workers must never share one writable SQLite database over SMB.

## 21. Security

Minimum requirements:

- secrets excluded via .gitignore;
- no Telegram token in source;
- no anonymous remote administrative API;
- confirmation for destructive commands;
- subprocess arguments sanitized;
- downloaded files verified where practical;
- migrations version-controlled;
- backups before destructive migration;
- service installation requires administrative privileges;
- cluster communication, when added, uses authenticated requests and replay protection.

## 22. Testing Strategy

Testing is required at multiple levels.

Unit tests:

- coverage math;
- conflict resolution;
- dataset requirements;
- strategy registry;
- state transitions;
- checkpoint compatibility;
- resource decisions.

Integration tests:

- fresh empty database;
- reuse old database;
- partial history;
- overlapping history;
- intentional gaps;
- duplicate API records;
- interrupted sync;
- locked database;
- simulated 429/5xx;
- invalid/corrupt candidate DB;
- strategy version change.

Windows smoke tests:

- install;
- start;
- Telegram controller;
- stop;
- restart;
- forced worker termination;
- reboot recovery;
- uninstall while preserving data.

CI must not depend on live Bybit availability for ordinary regression tests.

A separate explicit/manual live smoke test may use Bybit.

## 23. Migration from Existing Project

Existing working behavior should be preserved as reference, including:

- historical SQLite data;
- strategy/backtest semantics;
- checkpoint/resume behavior;
- Telegram controls;
- NSSM restart policy;
- progress logging.

Migration approach:

1. port behavior into modular components rather than copy one large script unchanged;
2. add regression tests around important existing semantics;
3. create legacy database recognizers/migrations;
4. preserve old files until the new implementation validates equivalent behavior.

## 24. Milestone Order

### Milestone 1: Standalone Foundation

- repository skeleton;
- config;
- installer;
- runtime bootstrap;
- local SQLite state;
- logging;
- Windows service wrappers;
- doctor.

### Milestone 2: Resilient Market Data

- legacy DB discovery;
- schema versioning;
- coverage index;
- idempotent sync;
- gap repair;
- retries;
- integrity tools.

### Milestone 3: Strategy Plugin Engine

- strategy interface;
- registry;
- requirements;
- versioning;
- executor;
- result identity.

### Milestone 4: Scheduler and Recovery

- durable jobs;
- dynamic workers;
- RAM-aware scheduling;
- checkpoint/resume;
- controlled shutdown.

### Milestone 5: Telegram Operations

- status;
- lifecycle commands;
- sync/repair;
- strategy management;
- confirmation flows.

### Milestone 6: PostgreSQL Backend

- optional PostgreSQL state store;
- migration from local state;
- preparation for cluster mode.

### Milestone 7: Cluster

- master;
- node agents;
- task leases;
- heartbeat;
- authenticated LAN communication;
- distributed results.

## 25. Non-Goals for Initial Milestone

The first milestone does not need:

- Kubernetes;
- mandatory PostgreSQL;
- shared writable SQLite over LAN;
- automatic historical L2 reconstruction;
- complex web UI;
- destructive automatic cleanup.

These can be added only after the standalone service is proven reliable.

## 26. Success Criteria

The standalone foundation is successful when a second Windows PC can:

1. clone the repository;
2. run one installation command;
3. detect a valid pre-existing Bybit SQLite archive or create a new one;
4. initialize its environment automatically;
5. install controller and worker services;
6. recover from reboot and worker crash;
7. update data without duplicates;
8. resume interrupted work;
9. execute registered strategies;
10. expose useful Telegram status/control;
11. produce persistent logs;
12. preserve all market data through reinstall/uninstall unless explicit deletion is confirmed.

