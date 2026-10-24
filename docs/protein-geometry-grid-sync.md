# Grid / Strattester structural research synchronization

Grid unified_features.py selects GOOD historical rows for warm-start and
resets per-symbol rolling state on a one-minute gap. It aligns optional
microstructure by event timestamp and records feed capabilities separately.

Required before cross-system integration:
- Canonical exchange, market type, instrument and timeframe identity.
- Explicit conversion between Grid datetime ts and Strattester integer ms.
- GOOD, eligible, complete and watermark gates.
- Atomic snapshots of relevant PostgreSQL and SQLite/sharded data.
- Causal availability-time checks, including late-arriving revisions.
- Missing bars, clock skew, restart/replay and stale-feature tests.
- Immutable dataset and model version hashes.
- Separate ML worker; no live trading until walk-forward acceptance.

Current Grid synchronization is NOT end-to-end verified. Existing standalone
geometry code does not consume Grid features.
