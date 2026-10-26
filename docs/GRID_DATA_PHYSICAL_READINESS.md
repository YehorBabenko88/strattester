# GRID_DATA_PHYSICAL_READINESS — independent evidence review (2026-10-24)

## Scope and exact references
- Strattester PR #21 reviewed at 67301726d250973602b964adabdb9eb8d50d0f13.
- Independent branch: parallel/alphafold-data-sync, Draft PR #17.
- Grid inspected at accessible default-branch grid/features.py; **Grid exact HEAD and PostgreSQL DDL not attested**.
- No physical LS5/PC4, PostgreSQL or production database was accessed.

## Confirmed source facts
- Strattester marketdata/schema.py SCHEMA_VERSION=2: candles PK(symbol,timeframe,open_time), complete integer; auxiliary mark_prices, index_prices, premium_index, open_interest, funding, long_short_ratio, public_trade_aggregates. No ingestion/availability/revision/producer/market_type columns in candles.
- marketdata/sqlite_store.py SQLiteMarketStore.open creates directories, initializes/migrates schema, configures WAL and writes schema_meta: **not safe as a read-only exporter**.
- marketdata/store_factory.py routes to ShardedMarketStore if configured.
- marketdata/sharded_store.py uses sanitized symbol, SHA256-derived bucket and manifest READY state; falls back to legacy by coverage and may open/create a shard when none found. Routing must be frozen and attested by producer before export; a consumer cannot infer authoritative history from filesystem paths.
- PR #21 financial_contract.py Bar uses exchange+market_type+symbol, timeframe_ns, candle_open/close_ns, event_ns, ingest_ns, available_ns, watermark_ns, quality VERIFIED, eligible, complete, revision, producer and source_sha. Snapshot.coherence_id is a caller assertion, not evidence of a coherent Grid export.
- Grid grid/features.py treats quality_status GOOD as eligible, unlike PR #21 VERIFIED. Do not silently map them.

## P0 blockers
1. No independently verified Grid PostgreSQL DDL, schema version, PG cluster identity, MVCC snapshot/LSN, producer epoch, or export implementation. No claim of coherent PG+SQLite history is possible.
2. Ordinary Strattester SQLite candles lack ingest_ns, available_ns, watermark_ns, revision, market_type and producer. These fields MUST NOT be inferred from event/open time, file mtime, or the current clock.
3. PR #17 experimental reader assumes a synthetic table with columns absent from ordinary Strattester DDL. It must not be wired directly to production storage.
4. Manifest-only SHA256 shape checks and coherence_id do not prove origin, completeness, immutability, source ownership or cross-source atomicity.
5. Historical UPSERT of existing candle PK can overwrite a previous version; absent retained history, as-of reconstruction is impossible. Fail closed for historical backtesting requiring revision provenance.

## P1 blockers
- Freeze symbol-to-shard routing and manifest generation before any export. Include dataset, timeframe, market identity and source authority, and require source-specific immutable export receipts.
- Verify writer concurrency with SQLite WAL snapshot and PG REPEATABLE READ / exported MVCC snapshot, then verify source identity and epoch stability at end; retry or reject on movement.
- Reject unknown quality enum, missing candle completeness, gaps, duplicate/revised bars, late availability, schema mismatch, and inconsistent clock units.
- Use no-write SQLite URI and never invoke SQLiteMarketStore.open() in an export consumer.
- Atomic staging, fsync, content hash, immutable rename and attestation signed by an authorized producer; consumer verifies signature and byte digest before parsing. A digest alone is not producer authentication.

## P2
- Include independent crash/rollback/restart tests, WAL checkpoints, malicious paths, TOCTOU and schema drift.
- Require deterministic canonical encoding, resource ceilings and provenance of every transform.
- Audit ordinary research/runner and sync ingestion/coverage path with synthetic fixtures.

## Producer-issued immutable export contract v0 (PROPOSED, NOT IMPLEMENTED)
Producer must create an immutable snapshot export from a **consistent source-owned transaction**:
- protocol_version, producer_id, producer_build_sha, signing_key_id, signature_algorithm, signature;
- export_id, coherence_epoch_id (issued by producer/coordinator), created_at_ns, as_of_knowledge_ns;
- source receipts: source_id, engine, cluster/system identity, database/schema version, manifest generation, shard route, transaction/LSN/snapshot identifiers (where applicable), source event watermark, availability watermark, completeness attestation;
- partition identity: exchange, market_type, symbol, dataset, timeframe_ns, UTC unit and candle boundary convention;
- immutable artifact: canonical serialization version, byte_size, sha256, row_count, min/max event and availability timestamps, revision policy and gaps report;
- attested source selection and explicitly recorded exclusions; source set must match required source set exactly.

Acceptance requires trusted signature verification, exact bytes/digest, schema identity, non-ambiguous source authority, knowledge-time cutoffs, and independent consistency checks. **Never synthesize missing ingestion, availability, revision, watermark, epoch, or historical versions.**

## Evidence limits and decision
Read-only source inspection only. No PostgreSQL DDL or Grid exact HEAD independently confirmed. No physical or synthetic cross-database concurrency tests executed in this review. Verdict: BLOCKED / NO-GO. No G1, merge, live trading or production DB writes.

## Cycle 2 pinned-source assessment (supersedes source-inspection uncertainty above)

Actual Grid source commit **d537d525296ef34f727996e240ae6c60102c6082** was inspected via exact Git blobs. `grid-pinned-source-assessment.json` records SHA256 and byte counts for eight inspected blobs. These are **auditor source-inspection receipts**, never producer-issued export receipts. They attest source text only; no deployed DDL or physical database was queried.

| Fact | Pinned source evidence | Readiness consequence |
|---|---|---|
| Source DDL | `grid/db.py:15-42`; `grid/migrations.py:19-32,92-113` | Source DDL inspected; actual applied schema, system identity and migration state NOT_RUN. `market_events.ingest_ts` exists; it does not establish candle first availability or version history. |
| Revision writes | `grid/storage.py:144-180` | Larger trade-count candle replaces current value; accepted footprint deletes old levels and replaces them. No retained revisions for historical knowledge cuts. |
| Transaction boundary | `grid/storage.py:145-180,184-214` | Candle and footprint share a transaction. Feature building, persistence and derived processing follow outside that transaction; no atomic all-dataset cut established. |
| WAL | `grid/segment_wal.py:173-219` | Ordered ACK and compaction support pending-write recovery. ACKed segments can be removed; this is not a retained revision/availability ledger. |
| Completeness | `grid/control_state.py:3-25` | Consumer progress drives retention safety; it does not certify producer event or availability completeness. |
| Availability | `grid/level_generator.py:43-46` | `available_ts` is declared period end. It cannot be promoted to first knowledge timestamp. |
| SQLite boundary | `grid/legacy_working_copy.py:4-16` | Single-file SQLite backup does not certify PG+SQLite coherence or frozen shard routing. No SQLite file was opened by this audit. |
| Market identity | `grid/db.py:28-42`; `grid/config.py:15` | Candle keys lack venue/market type. Default linear endpoint does not prove each historical row's market authority. |

`strattester.research.grid_producer_readiness` exposes a deterministic BLOCKED assessment, strict exact-source-byte verifier, and a native-export guard that always raises before physical IO. It accepts no supplied availability, revision, epoch or eligibility claims and constructs no Snapshot. No native exporter can truthfully issue the required historical manifest at this source pin. A valid signed manifest consumer does not remove these native producer blockers.

Tests: 11 independent assessment/guard cases passed locally, including source-pin, membership, digest, byte-type tampering and attempted caller override. A separate read-only exact-Git-blob check verified all eight receipts against the actual pinned Grid checkout and returned BLOCKED. Existing specification reference tests are separately exercised. CI at this branch's eventual exact commit must be reviewed independently; local tests do not establish hosted CI or physical readiness.

Physical PostgreSQL/SQLite data reads, applied DDL queries, WAL/MVCC concurrency, shard freeze, crash/restart, signing deployment, source completeness and native immutable export: **NOT_RUN / BLOCKED**. No service, migration, checkpoint, dependency installation, G1 or production write was performed.
