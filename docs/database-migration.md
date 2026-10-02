# Database migration

Legacy market databases must be inspected read-only first. Discovery must not create a missing SQLite file. Keep the original database until integrity, schema recognition, coverage and a bounded Strattester run have succeeded.

The large market-data database remains independent from code releases and from optional PostgreSQL state.
