# Read-only results boundary 1.0 — source qualification BLOCKED

Frozen source base: `37ff7e9d12a4d2dccd788fc493c28557dbe8bcea`.
Integration work order: unified-system `50e6e63cb183f6dcf1dee3c753f966717ee3b110`.

`strattester.readonly_api.ReadOnlyResultsApp(source_path)` is an opt-in WSGI
callable. It starts no listener, worker, service, exchange connection, or native
operation. Hosting, authentication and deployment remain separate work.

All replies contain `api_version: "1.0"`, `producer: "strattester"`,
`read_only: true`, `provenance: "UNAVAILABLE"`, and `status`.

| GET route | Response |
| --- | --- |
| `/internal/v1/capabilities` | 200, status AVAILABLE; capabilities historical_research/runs/run_metrics are all false |
| `/internal/v1/health` | 503, status UNAVAILABLE |
| `/internal/v1/runs` | 503, status UNAVAILABLE |
| `/internal/v1/runs/{id}/metrics` | 503, status UNAVAILABLE |

503 reason is SOURCE_UNAVAILABLE for absent/unreadable/incompatible SQLite,
otherwise SOURCE_PROVENANCE_UNQUALIFIED. A reachable source is not a qualified
historical dataset. No metrics, trades, run identities or timestamps are emitted.
No zero/empty successful result is fabricated. Capability availability describes
the contract, not source readiness. Clients must check individual capabilities.

Runs accepts decimal `limit` 1..100 (default 50) and `offset` 0..10000
(default 0). Query length is capped at 256 and fields at two. Repeated, unknown,
malformed or out-of-range fields return 400 INVALID_QUERY. Other recognized
routes accept no query fields. Run IDs use `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`.
Unknown routes return 404; all non-GET methods return 405 with Allow: GET.
Replies are no-store JSON. Source queries use SQLite mode=ro, query_only and
100 ms lock timeout with LIMIT 1; no ResultStore.open, migrations or result
deserialization. No source paths, query values, database errors or credentials
are returned or logged.

## Why successful results are blocked

At the frozen base, `persistence/result_store.py:12-15` has no dataset identity,
history interval or immutable seal. `put` at lines 29-35 and staged promotion
replace rows for an existing composite run key. `created_at` is floating point
seconds from time.time, not a strict UTC integer-millisecond source field.
`research/result_persistence.py:12-16,20-25` saves strategy fingerprint and an
unconditional COMPLETE_HISTORY label. `strategies/base.py:27-33` hashes strategy
code/requirements, not actual consumed data. `research/runner.py` knows requested
history bounds, but those bounds/data identity do not reach result persistence.
Existing job lease fencing protects publication authority, not dataset identity.

The fake SQLite regression demonstrates overwrite and absent dataset identity,
then checks all source routes fail closed without changing database bytes.
It is synthetic evidence only.

Before enabling results, producer work must persist immutable per-run and dataset
identities with verified historical provenance and UTC integer milliseconds,
reject conflicting reuse, and define snapshot/pagination and release identity.
A SHA of mutable rows cannot establish those missing facts. The integration
handoff requires SEALED dataset_fingerprint and historical_research; this API
does not claim to satisfy that successful-result contract yet.

SYNTHETIC testing is separate from HOSTED CI and PHYSICAL acceptance. Physical
G0, native G1 Execute/Cleanup, live trading and deployment are NOT_AUTHORIZED.
