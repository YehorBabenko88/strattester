# Versioned history exporter engineering prototype

`strattester.research.financial_grid_exporter.export_history` accepts only the
`SEALED_VERSIONED_HISTORY_V1` profile. The pinned native Grid implementation
`d537d525296ef34f727996e240ae6c60102c6082` remains **BLOCKED**: its latest-state
DDL does not retain first availability, revisions, or coherent source epochs.
An unsupported profile fails before filesystem or physical database access.
This module does not migrate a native database or manufacture those facts.

The supported adapter reads SQLite WAL databases or PostgreSQL in one read-only
REPEATABLE READ transaction per source. SQLite uses mode=ro, query_only, and a
read transaction; it never uses immutable=1 on a live WAL database. PostgreSQL
uses the explicit caller DSN, read-only repeatable read, a connection timeout,
and a five-second statement timeout. No installed database service is managed.
PostgreSQL requires the existing `postgres` optional dependency.

## Trusted profile and source contract

A `HistoryProfile` contains an explicit shared epoch, integer knowledge cutoff,
source membership, and scope. Each frozen `HistorySource` pins source ID, engine,
location, snapshot ID, canonical logical content seal, and disjoint market
partitions. The profile must come from an independently trusted producer/owner;
copying values from the database into a profile does not establish truth.
Equal timestamps cannot substitute for the pinned epoch and seals.

The source schema is exactly `DDL` in the module: one TEXT payload column in
`history_meta` and `history_rows`, both NOT NULL. `SCHEMA_SHA256` is the canonical
DDL digest. A single metadata JSON record contains source/snapshot/epoch IDs,
schema digest, complete/first_availability_retained/revision_history_retained
boolean facts, event/availability watermarks equal to this cut, and the ordered
partition list. Each row JSON has `bar` (the complete typed Bar record),
`first_available_ns`, `source_id`, and `coherence_epoch_id`.

Every version is retained. Revisions must start at one, be contiguous, have
strictly increasing availability, and share first_available_ns equal to the first
revision's available_ns. All versions, including versions after the requested
cut, participate in the external content seal. Export chooses the final revision
available at the cut and validates the immutable typed Snapshot. Missing market
partitions, gaps, bad provenance, malformed schema, changed seals, mixed epochs,
and overlapping shard routes fail closed. SQL row order does not affect seals.

`history_seal(meta, rows)` defines the canonical raw logical SHA256 preimage. It
is not a hash of live SQLite/PG physical files; no live working database is copied.
This engineering profile trusts externally sealed historical assertions. It
cannot prove a dishonest producer retained every historical event, and does not
qualify the unknown native physical databases for production or G1.

## Artifacts and signing

`export_history(profile, new_output_directory, producer_id=..., producer_build_sha=...,
key_id=..., export_id=..., issued_at_ns=...)` returns `ExportArtifacts` containing
a frozen Snapshot, directory, and exact SHA256s. It publishes snapshot.json,
unsigned-manifest.json, and provenance.json together by renaming a staged sibling
directory on the same filesystem. A retry rereads and verifies every externally sealed source, recomputes all three
artifact bytes, and returns a completed destination only when its exact file
membership and bytes match. It never trusts hashes stored alongside the output.
Partial, conflicting, or additional files are rejected without overwriting. Failed
or cancelled exports leave no published directory. Rows and raw/snapshot bytes have
hard 100,000 / 8 MiB limits. Cancellation is checked during source reads and
publication. Callers must use a trusted output parent; hostile concurrent Windows
namespace changes still require native handle-relative confinement. Failed export
and signer stages are preserved with a sibling non-authoritative cleanup inventory;
no recursive deletion is attempted. Public RFC signing scratch is also preserved
with an inventory. Interrupted-before-publication scratch is never trusted for
recovery; a retry recomputes from the source seals.

The manifest exactly matches the signed consumer schema except signature_b64.
Production signing/key provisioning remains owner work. `sign_rfc_test_export`
uses only the public RFC8032 test seed and refuses any scope/identity except
SYNTHETIC_ENGINEERING_ONLY, fixture-grid, rfc-key. It verifies the pinned OpenSSL
binary hash, verifies its own signature, and atomically publishes signed-test
with manifest.json and a detached signature.ed25519. The existing consumer still
requires a separately pinned trust store, policy, and OpenSSL verifier. Test keys
establish engineering interoperability, never native historical correctness.

## Verification

`python -m pytest tests/research/test_financial_grid_exporter.py -q --basetemp=<new-task-path>`

The PostgreSQL integration test creates its own initdb cluster beneath pytest's
task temporary directory, chooses a free nondefault loopback port, starts one
owned child postgres process, and stops only that cluster via its exact data
directory. It never discovers, starts, stops, or connects to an installed service.
Set PG_BINDIR (or STRATTESTER_TEST_PG_BIN) to the PostgreSQL binary directory.
Discovery also supports installed Windows18 and Linux /usr/lib/postgresql/*/bin.
An explicit missing binary directory or CI without binaries fails the test; an
optional local run without installed binaries/dependency explicitly skips. The fixture proves MVCC returns the old externally sealed
view despite a concurrent writer; a subsequent transaction observes the changed
content and fails the old seal. SQLite and sharded fixtures verify corresponding
seal, history, routing, cancellation, budget, replay, and native-block boundaries.

Verified on 2026-10-26 with the designated `work/financial-venv/Scripts/python.exe`
(Python3.12.10, torch2.14.1+cpu, NumPy2.5.4): exporter, signed-export consumer,
and native-readiness tests: **38 passed in 36.25s**, no skips; snapshot and export
spec reference tests: **20 passed in 0.27s**. The task-owned PostgreSQL18.6 fixture
used loopback port52939 and PID70576; its log records ready and complete shutdown.
PostgreSQL executable SHA256:
`14817df435104dcfe05ad8343fda200930abf778553ab60154bd285aea6833e1`.
The OpenSSL test signer/verifier executable SHA256:
`78340fb01dea2df5caab73dcf28833b31329226a4c9e02f717f1d399592265b9`.

Psycopg and psycopg-binary3.3.6 were installed in that designated venv; both
installed distribution metadata report `LGPL-3.0-only`. The initial exploratory
run installed the same dependencies into system Python3.14 as well (including
its tzdata2026.5 dependency); its broader signed-export tests failed setup because
that interpreter has no torch. No ML success is attributed to Python3.14. No
production database or installed PostgreSQL service was used by either run.


Replay follow-up verification: the new completed-export test first failed against
the original destination-exists behavior (1 failed, 4 passed). It uses a separate
child process that publishes then calls os._exit(17), losing its return value; the
retry rebuilds from source and verifies the completed bytes. Added partial, extra
file, conflicting snapshot with updated colocated hashes, and changed-source
retry rejection cases. Failure-stage tests verify preserved inventory, not deletion.

Final follow-up designated Python3.12 run: exporter/signed-consumer/native-readiness
**43 passed in 14.70s**, including all18 exporter cases and the real disposable
PostgreSQL MVCC fixture, with no skips. `git diff --check` passed.
