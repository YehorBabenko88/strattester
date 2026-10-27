# Parallel Grid schema identity audit

Pinned Grid main was rechecked with `git ls-remote` on 2026-10-27 and remains `d537d525296ef34f727996e240ae6c60102c6082`. All eight audited source bytes match the existing readiness SHA-256 receipts; Git blob identities are recorded in parallel-grid-source-audit.json. No Grid source was executed or database contacted.

The actual `grid/db.py` DDL stores latest candles under `(symbol, ts)` and derivatives metrics, including a funding-rate value, under `(symbol, ts)`. `grid/storage.py` replaces accepted candle fields on conflict and deletes superseded footprints. `grid/segment_wal.py` checkpoints acknowledgments and reclaims segments; replay durability does not establish retained historical knowledge. The migration DDL does not make those latest-state records a complete first-availability/revision/coherence archive. Native PostgreSQL, shards, MVCC and WAL history export remain BLOCKED. Funding history is not invented or inferred from current funding-rate fields. Signatures authenticate bytes, not historical completeness.

Confirmed defect: the sealed synthetic SQLite exporter checked only table DDL, accepting unpinned views, indexes and triggers while claiming physical schema identity. The reader now compares a bounded complete sqlite_master object list against precisely the two pinned table objects. Additional schema objects fail before payload reads and publication. Logical content seals and the externally attested source facts remain required. PostgreSQL behavior is unchanged and unverified in this task.

Independent disposable fixtures cover views, indexes and triggers for both sqlite and sharded_sqlite, plus exact-schema success. RED: 6 failed, 2 passed. GREEN: 94 passed, 36 deselected, zero failures/skips across the new test and existing Grid suites using `-k "not postgres"`. The deselection intentionally excludes every PostgreSQL-named case, including mocked cases; no local PostgreSQL service/server/daemon was run. New basetemps were outside the checkout. `git diff --check` passed.

Logs outside the checkout:
- `../parallel-grid-red-20261027.log`: SHA-256 `347c727a6e9133b3b353c6599b14dbebec52676686e820b3ba3320f0721bb3f0`
- `../parallel-grid-green-20261027.log`: SHA-256 `b391c53be3cfd1fdb150615877ae4bceac35611301081ded1392568d5717c969`

G1 Execute and Cleanup: NOT_AUTHORIZED. Deployment and Trading: NO-GO. No production/native/physical/service/credential or blocked-stage workaround activity was performed.
