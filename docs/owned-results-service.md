# Private owned results service

`strattester.owned_results_service` wraps the existing `ReadOnlyResultsApp`; it starts no strategy engine, worker, scheduler, migration, training or promotion. Default invocation is Prepare: it prints status and does not open a database or bind a socket. Only explicit `--serve --store ABSOLUTE_EXISTING_DB --port PORT` listens, on IPv4 loopback only.

Serve must run through the externally pinned Unified `unified_system/owned_python.py` raw script with Python `-I -S -B`, Strattester's checkout as `--source-root`, Unified's checkout as an explicit `--dependency-root`, and module `strattester.owned_results_service`. The trusted launch profile supplies:

- `UNIFIED_SOURCE_ROOT`: the trusted Unified checkout, not Strattester.
- `UNIFIED_SOURCE_COMMIT`: exact Strattester HEAD; `UNIFIED_ROOT_SOURCE_COMMIT`: exact Unified HEAD.
- `UNIFIED_GIT_EXECUTABLE` and `UNIFIED_GIT_SHA256`: the externally pinned Git binary used by shared `SourceFence`.
- `UNIFIED_MODULE_ID=strattester`, numeric `UNIFIED_MODULE_VERSION`, bounded `UNIFIED_RELEASE_ID`, private 64-lowercase-hex `UNIFIED_INSTANCE_TOKEN`.
- `UNIFIED_PRIVATE_CACHE_ROOT`: a pre-existing private cache directory outside both source checkouts.

The external ProcessDriver must pin the bootstrap, shared source guard and dependency files before execution. The application cannot authenticate its own verifier. Startup verifies both source pins with the shared Unified `SourceFence` in a separate raw-bootstrap child with a deadline and process-tree termination. No alternate source policy is implemented here. The pinned shared policy admits its fixed safe capsule devnull attributes/hooks configuration; incompatible source metadata rejects startup rather than relaxing verification. Native Windows process-tree termination and confinement remain unqualified until hosted/native acceptance.

Every route requires one exact `Authorization: Bearer TOKEN` header. GET `/internal/v2/module/health` rejects query strings and returns exactly `module_id`, `version`, `release_id`, `instance_token`, `ready`; HTTP200 means the configured store's required real tables/columns and bounded read-only transaction/query succeeded. HTTP503 means unavailable. Health establishes module/store readiness, not trusted research data or freshness. A checkpointed file uses immutable read-only mode; a live WAL uses mode=ro with its existing checked regular WAL/SHM files so committed WAL schema is visible. The adapter never creates a ResultStore or sidecar.

Existing `/internal/v1/*` route responses and producer/receipt qualification remain owned by `ReadOnlyResultsApp`. Optional `STRATTESTER_RESULTS_TRUST_JSON` has exact `sources` and `receipts` arrays (at most64 entries each), containing the same externally admitted identity triples and receipt quadruples accepted by that API. Empty policy discloses no research records. No trust is inferred from a healthy database, hashes or local completion alone. This configuration is owner policy, not signature authentication.

Transport is a single-threaded bounded-backlog stdlib HTTP service with an absolute per-request deadline plus socket timeout, no request logs and no non-GET operations. It is intended for a private local ProcessDriver, not Internet exposure or availability guarantees. The source verdict is cached at startup; the external Driver's file pins supply ongoing code-integrity checks. SQLite path checks do not provide native race-proof filesystem confinement.

All physical deployment is NOT_RUN. There is no all-six qualification, live-order authority, training permission, scientific promotion or physical/HA attestation.

Windows verifier timeout cleanup invokes the explicit `SystemRoot/System32/taskkill.exe` path, never a PATH-selected taskkill. This is a bounded cleanup attempt, not a verified native Job Object containment guarantee; hostile descendants or OS cleanup failure remain native qualification blockers. WAL presence uses checked lexical paths and lstat before any target-following probe; the same helper is shared by adapter readiness and existing read-only result/metadata routes.
