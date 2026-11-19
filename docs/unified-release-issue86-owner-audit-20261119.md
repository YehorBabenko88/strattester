# Strattester UNIFIED RELEASE owner audit — Issue #86 (2026-11-19)

Status: **SOURCE-ONLY / PARTIAL / NO_GO**. Parent: YehorBabenko88/unified-system#111. This is an ownership and migration plan, **not** a production qualification or approval to delete legacy storage.

## Immutable observed baselines

- `strattester/main`: `37ff7e9d12a4d2dccd788fc493c28557dbe8bcea`.
- Research candidate PR #83: `d6293f75db7fcc8eed0900521a1ba6bd46b3468e`, stacked on `codex/mwi-engine-stage2-20261112`. This is **not** main.
- Security CI PR #84: `731f325a505ff18720c550aa0dc762ed54dd537b`, based on main. It is **not** merged.
- Read-only CI observation: PR #83 head had `tests` and `MWI contained offline research` concluded success; PR #84 head had `tests` concluded success. Neither proves production E2E or the present audit head.
- Prior cross-repository inventory: Unified PR #109, `docs/security/five-repository-boundary-audit-20261118.md`; its five-repo static scan did **not** establish security clearance.

## Observed code boundaries (PR #83 exact source)

| File / symbol | Observed function | Owner decision | Disposition |
|---|---|---|---|
| `strattester/marketdata/bybit_client.py:BybitClient.get/fetch_klines/fetch_linear_instruments` | Sends public Bybit REST requests; own retry/session | **Grid** canonical exchange ingestion | **DUPLICATE FUNCTIONALITY; retain pending import graph + Grid parity** |
| `strattester/marketdata/sync_engine.py:SyncEngine._sync_rows/sync_requirement` | Calls client and writes candles, price klines, OI, funding, long/short ratio to local store | **Grid** owns canonical history writes; Strattester owns **readiness requirements** | **SPLIT REQUIRED; do not remove without migration** |
| `strattester/marketdata/readiness.py:ensure_history/ensure_instrument_history` | Instantiates local SyncEngine and can trigger fetch/write | Strattester readiness policy, **Grid** fetch/writes | **ADAPTER SEAM; currently not read-only** |
| `strattester/marketdata/store_factory.py:open_market_store` | Creates SQLite or sharded market stores | Grid canonical raw; Strattester may retain experiment-local caches | **UNKNOWN usage; preserve** |
| `strattester/marketdata/l2_recorder.py:L2AbsorptionDetector` | Computes L2 absorption from a book | Strattester research or Meta Analyse analytical owner **pending MASTER** | **NOT an observed live recorder; do not infer from filename** |
| `strattester/persistence/result_store.py:ResultStore` | Local persisted experiment result storage | **Strattester** | **KEEP**, preserve replay/crash semantics |
| `strattester/research/result_persistence.py:persist_report_fenced` | Fenced research result publication | **Strattester** | **KEEP**, verify lease/identity/atomicity |
| `research/mwi_offline/mwi_offline/simulation_adapter.py` | Offline research simulation adapter | **Strattester** | **KEEP** as candidate; synthetic evidence is not real market validation |

This inventory distinguishes functional overlap from byte-identical duplication; no exact-byte Grid/Strattester duplicate is asserted.

## Proposed single-owner contract, requiring MASTER and Grid ACK

1. Grid publishes versioned, immutable, read-only dataset snapshots with `exchange`, `market_category`, `symbol`, `instrument_id`, `dataset_kind`, `timeframe`, `start_ms`, `end_ms`, `source`, `source_timestamp_ms`, `ingested_at_ms`, `closed`, `coverage`, `gap_count`, `snapshot_id`, `content_sha256`, `schema_version`, and source-quality status. Exact field names/ABI require owner ACK.
2. Strattester requests a snapshot, verifies source hash/identity, continuity, candle closure and point-in-time cutoff, then runs deterministic replay, backtest, walk-forward and paper-only experiments. It must **never** silently fall back to its own Bybit client or mutate Grid's raw store.
3. Strattester emits a versioned immutable experiment artifact with dataset snapshot digest, strategy/config digest, seed, software SHA, UTC decision cutoff, fees/funding/slippage assumptions, OOS split, result hash and `execution_mode=PAPER_ONLY`. Terminan reads this via the shared Gateway; Math owns verified numerical kernels.
4. Missing Grid data, incompatible ABI, missing provenance, lookahead, mixed instruments, gaps, partial/live-unknown source or nonfinite outputs must fail closed; never label synthetic results as live.
5. Existing SQLite, sharded data, raw evidence and results remain untouched until parity, crash/restart, rollback and exact-head Windows CI demonstrate safe migration.

## Release blockers and next executable checks

- **P0**: actual full import/call graph and all open PR/non-main branch lineage still unqualified. PR #83 is stacked; passing CI does not imply merge readiness.
- **P0**: Grid immutable snapshot/read-only API and authority/identity contract not yet jointly approved.
- **P0**: complete `git --all` historical secret scanning (gitleaks/trufflehog), dependency/CodeQL and native Windows ACL verification **not performed** in this audit. Do not publish secrets.
- **P0**: no demonstrated real Bybit history -> Grid snapshot -> Strattester paper backtest -> Math -> Terminan E2E with restart, source receipts and rollback.
- **P1**: characterize local marketdata stores and all call sites before moving ingestion; add offline adapter contract tests for source identity, gaps, point-in-time cutoff, and no network/write fallback.
- **P1**: exact-head CI for this audit PR remains pending; no code/runtime changes in this PR.

## Preservation / removal decision

**Keep:** backtest/replay, strategy lifecycle, experiment/result ledger, fenced persistence, reproducible research tests and historical data. **Candidate to replace only after verified parity:** Strattester-owned REST ingestion and canonical raw-market writes. **Unknown / no deletion:** L2 absorption analytics, SQLite/shard compatibility and all stacked research PRs.

No branch purge, DB mutation, service installation, order placement, production permission changes or main merge is authorized. Final release status: **NO_GO**.
