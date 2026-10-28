# Native Grid catalog observations

`strattester.research.grid_source_capabilities.inspect_native_grid` inspects an
explicit SQLite/sharded SQLite source or credential-free PostgreSQL endpoint.
It reports catalog facts while always returning `status=BLOCKED` and
`eligible=False`. It cannot issue an export, a market-data seal, a coherence
epoch, a producer receipt, or authorization. The existing native export guard
still rejects before database access.

The implementation is bounded to 2,048 catalog rows, 1 MiB of canonical catalog
output, fixed cell limits, a five-second inspection budget, and cancellation.
SQLite uses `mode=ro`, `query_only`, `trusted_schema=OFF`, a read transaction,
and a progress handler. PostgreSQL uses an explicit endpoint with the existing
no-discovery policy, `REPEATABLE READ READ ONLY`, a pinned search path, one-second
statement/lock timeouts, and bounded queries. It never reads market table rows.
Only a verified ordinary `schema_migrations` table is read for at most 47 bounded
version/name claims. A view or an RLS-enabled lineage table is not trusted.
There is no service discovery or service management in production code.

The PostgreSQL reader locks the lineage relation before catalog inspection or
establishing its catalog snapshot, and then binds its resolver/catalog OID and
held relation lock. Two-connection tests prove that concurrent rename/view
replacement cannot slip between catalog inspection and a later lock. A separate
namespace-replacement test changes the containing schema after the OID recheck.
The final claim query uses `ONLY`, an expected `tableoid`, and
`TABLESAMPLE pg_catalog.system(100)`: PostgreSQL rejects a view at parse analysis
before evaluating its expressions, while the 100-percent block scan preserves
all ordinary-table claims. An absent relation remains unverified; no table is
created. These checks do not establish a producer epoch or data-history seal.

`catalog_sha256` fingerprints the observed catalog projection. It does not hash
market contents or live database bytes and cannot be supplied as a history seal.
`source_commit` names the source audit baseline, not the deployed producer build.
Matching columns, primary keys, and migration claims recognize a limited adapter
shape; full physical schema identity and deployed build identity remain missing.
Indexes, defaults, functions, and every deployment extension are not qualified.

## Source facts and remaining blockers

Local Grid HEAD and remote `origin` HEAD/main were independently read on
2026-10-26 at approximately 16:25 UTC. All were
`d537d525296ef34f727996e240ae6c60102c6082`. No Grid working database was opened.
No migration, service, or working Grid source was modified.

| Actual source | Observed behavior | Consequence |
| --- | --- | --- |
| `grid/db.py` | `market_events` has `event_ts` and server-default `ingest_ts`; its deduplicating insert has no candle revision linkage. | Event ingestion is observable, but cannot establish candle first availability or reconstruct revisions. |
| `grid/storage.py` | A larger trade count replaces the candle at `(symbol,ts)`; its accepted footprint is deleted and replaced. | Older candle/footprint versions are not retained by these tables. |
| `grid/migrations.py` | The registry contains versions 1–46. Version 8 adds derived `historical_levels.available_ts`. | Matching registry claims describe schema lineage, not retained first-knowledge history. |
| `grid/level_generator.py` | A derived level's `available_ts` is the aggregated period end. | This is a market-time availability rule, not the producer's first observation time. |
| `grid/segment_wal.py` | ACK checkpoints advance and fully acknowledged segments can be removed. | This is a recovery spool, not a complete immutable revision archive. |
| `grid/control_state.py` | Consumer watermarks track consumed-through progress; control state has its own mutable version counter. | Neither is a cross-store immutable historical-cut receipt. |
| `grid/retention_v2.py` | Eligible aged market rows can be deleted after required consumers advance, subject to holds. | Retention is not an unbounded replay-history guarantee. |
| `grid/legacy_bootstrap_import.py` and `grid/legacy_gap_repair.py` | Legacy SQLite candles are imported/repaired by market timestamp; conflicting OHLCV values are rejected. | No immutable first-availability/revision lineage or authoritative exchange/market routing is recovered. |

The PostgreSQL adapter verifies exact selected column order/type/nullability,
unmodified numeric precision, plain-table/RLS state, primary keys, and complete
version/name lineage. Missing, renamed, gapped, or unknown migrations and selected
schema drift result in `UNRECOGNIZED`. The legacy SQLite adapter recognizes the
concrete candle shape in Grid's own legacy-repair test. Grid does not provide an
authoritative deployed legacy DDL; recognizing that test shape does not assert
the shape of any real legacy database.

Cross-store coherence, authoritative exchange/market/shard membership, source
completeness, retained revisions, first availability, and producer-issued
immutable exports remain blocked. Equal cutoffs or matching catalog hashes do
not establish any of these facts. No producer history protocol is fabricated
for old latest-state rows.

## Reproducible contract fixtures

`tests/fixtures/grid_native_ddl.json` contains AST-extracted SQL from exactly the
following pinned blobs. It includes the complete database baseline, all 46
migrations, and the exact legacy SQLite test DDL. Tests execute that SQL only in
new disposable databases, never import or start Grid services.

| Pinned Grid path | Git blob |
| --- | --- |
| `grid/db.py` | `09ffb08fd955455a901dc09c5bbd06d19ee17228` |
| `grid/migrations.py` | `eb86864c8c523001740a8f2b0cdf7e160173b531` |
| `tests/test_legacy_gap_repair.py` | `7f4ca0408858a9b62c3c7702b1cca372757113bf` |

The fixture also records SHA-256 digests of the original source bytes. Other
audited behavior is pinned by these blobs:

| Pinned Grid path | Git blob |
| --- | --- |
| `grid/storage.py` | `da33a2fb80bb836bcf8e2b01c51228530f46ebe6` |
| `grid/segment_wal.py` | `87c1281be7a74d984913548f5f97cca1f54e052a` |
| `grid/control_state.py` | `36dae681892a009fe8170089a93760b86b24b14d` |
| `grid/level_generator.py` | `d784cec89b6a17e3680300cb9ecbefed0ea94de6` |
| `grid/legacy_gap_repair.py` | `57b63228ca222f26de79856535923ff9526e6f70` |
| `grid/legacy_bootstrap_import.py` | `e47b56a7dc547218df2074570c7821b00d834055` |
| `grid/retention_v2.py` | `585e2ceb76619154132188bc520a481ae8ca6097` |

The PostgreSQL tests reuse the reviewed fixture ACL/shutdown helpers. Each owns a
fresh data directory and loopback ephemeral port, initializes its own cluster,
executes the actual producer DDL, and stops exactly that owned cluster. No package
installation or existing database/service is involved. Native history, real OOS,
physical G1, production mutations, and trading remain unqualified.

Validation on Windows/Python 3.12.10, PostgreSQL 18.6, and psycopg 3.3.6:
the complete repository suite passed with **1,120 passed, 12 skipped, and 21
successful subtests**. All 23 new catalog cases passed. The skips are six native
CLI tests requiring `NATIVE_BROKER`, two native cache link/junction fixtures
requiring disposable-host/Windows privileges, two CUDA parity cases without
CUDA, and two artifact/data-source symlink fixtures without symlink privileges.
These prerequisites were not relabelled as passing or physically qualified.
