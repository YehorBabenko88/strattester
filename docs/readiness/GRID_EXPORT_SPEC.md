# Fail-closed Grid immutable export adapter specification v0.1

Status: SPECIFICATION / NOT A NATIVE PRODUCER IMPLEMENTATION. Production Grid remains BLOCKED.
Source Grid d537d525296ef34f727996e240ae6c60102c6082; Strattester baseline67301726d250973602b964adabdb9eb8d50d0f13. Physical DDL/migration state not queried.

## DDL comparison and forbidden inference

| Store | Source truth | Missing facts for historical research |
|---|---|---|
| Strattester SQLite legacy | candles.ts, symbol/timeframe/OHLCV | first availability, revisions, producer identity, exchange/market type |
| Strattester SQLite v2 | schema.py version2; candles.open_time, complete; funding_time/rate separate | ingest/available/watermark/revision/coherent epoch and producer signature |
| Grid SQLite legacy | candles.ts reader; producer-owned mutable files | immutable revision history, historical availability and cross-store cut |
| Grid PostgreSQL | db.py market_events event_ts/ingest_ts; candles_1m.ts; migrations quality_status, eligible, dataset_snapshots/hash/sample_count, consumer_watermarks | source-owned attested immutable cut, historical revisions/first availability; actual deployed schema unverified |
| Normalized research_bars | exact fields(Bar)+Instrument; temporary fixtures only | absent from real stores; not an adapter to those stores |

GOOD and VERIFIED quality enums MUST NOT be silently equated. Consumer watermark is progress, not producer completeness. Lease epoch is fencing, not a coherent data epoch. Existing PK UPSERTs can erase old revisions. No timestamp may be manufactured from mtime/current clock/close time. Millisecond→ns requires exact integer multiplication by1000000; reverse conversion rejects remainder. Candle close convention must be producer-declared (exclusive boundary versus exchange last-ms).

## Producer responsibility

The producer/coordinator owns the coherent cut and immutable export; the consumer cannot obtain it by independently copying live DBs. Use retained revision records and first_available_ns, source-owned consistent SQLite transactions and PostgreSQL MVCC/exported-snapshot identity, plus an actual cross-source epoch protocol. Independent per-file WAL transactions are insufficient. If these facts cannot be established, return BLOCKED and publish no usable Snapshot.

Signed canonical root manifest must bind protocol+canonicalization version, producer/build/key IDs and signature algorithm, export ID, monotonic epoch and replay policy, requested knowledge cutoff, exact required source set and market partitions (exchange/market_type/symbol/dataset/timeframe), and every source receipt. Trust keys come from an independently provisioned allowlist, never from the artifact. Owner signs proposed deployment trust policy separately.

Each receipt binds source engine+cluster/system/schema SHA/version, routing manifest generation and shard authority, transaction/snapshot/LSN identity as applicable, epoch, first-availability and revision-history retention attestation, event+availability completeness watermarks, quality/eligible/complete results, exact count/ranges/gap report, canonical artifact length+SHA256. Final signature covers all receipts and selection/exclusion decisions atomically. Epoch equality strings alone are not coherence proof.

Consumer verifies authorized producer signature over canonical entire manifest, replay policy and exact request/source/schema/market identities, consistent epoch and complete cut, artifact bytes/count/range/revisions and causal inequalities before any feature extraction. Missing/duplicate/extra source, partial publication, unknown quality, gap, unsupported revision policy, schema drift or uncertain source identity means BLOCKED. No source mutation, WAL checkpoint, schema migration or DB creation is a consumer operation.

## Independent contract evidence

`tests/research/test_grid_export_spec_reference.py` is a test-side independent conformance model:14 cases cover authentic fixture receipt, missing facts, stale epoch/watermarks/schema, hash/length tampering, producer forgery and missing/duplicate source membership. HMAC key is a public TEST fixture, not a production key or production signature solution. Existing financial_contract tests cover row causality/gap/identity/revision/quality. These tests do not prove actual Grid exporter, cross-DB atomicity, PostgreSQL MVCC, signatures, recovery or deployment behavior. No consumer API is promoted to producer authentication by these tests.

PR17 eab45b5 adds a consumer callback receipt verifier; reviewed, not imported because it does not provide native producer facts, exact multi-source membership or historical truth. Its protocol must undergo independent security review before deployment. PR18 afeab9e adds independent Decimal/time oracles; they do not implement an exporter. No upstream branches overwritten.
