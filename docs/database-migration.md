# Database migration

Legacy market databases must be inspected read-only first. Discovery must not create a missing SQLite file. Keep the original database until integrity, schema recognition, coverage and a bounded Strattester run have succeeded.

The large market-data database remains independent from code releases and from optional PostgreSQL state.

## Migration integrity

Promotion validates candle contents as well as coverage and auxiliary datasets.
A correction to an already copied candle keeps the symbol in MIGRATING until an
idempotent retry copies the corrected value. Final validation and promotion
share a manifest transaction with routed writes; waiting writers reselect the
authoritative store after promotion. Live writes must use ShardedMarketStore
routing rather than writing the legacy database directly during migration.
