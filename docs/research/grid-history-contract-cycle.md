# Ordinary Grid history contract cycle, 2026-10-26

This change starts from strattester commit
`c09592be649d249c6b082a5e21cbeea2800a0049`, tree
`a31bd16e8826f92e12a5211360c4d926e7f09673`.
The audited baseline blobs are:

| File | Git blob |
| --- | --- |
| strattester/research/grid_source_capabilities.py | 18beea55a7486210db2e40903c4ef725f2b6aaa8 |
| strattester/research/financial_grid_exporter.py | dd310b77c889a1bb6090b5572c3051113903e8b7 |
| tests/fixtures/grid_native_ddl.json | efb35b231a10a84ccffe285dfd107f9629963ce4 |

The existing DDL fixture pins native Grid commit
`d537d525296ef34f727996e240ae6c60102c6082`, including source blob and
SHA-256 identities. This cycle uses that fixture and the already recorded
source assessment; it does not claim a fresh remote or deployed-source check.

The native catalog observation remains BLOCKED. Schema or migration recognition
cannot recover first availability, overwritten revisions, source completeness,
authoritative market routing, deployed producer identity, or a cross-store epoch.
The sealed history protocol is an external producer contract, not an adapter
that manufactures those missing native facts. Signed receipts authenticate
producer assertions; their validity does not establish native historical truth.

A deterministic cancellation regression failed before the fix: after validation
of revision 1 activated cancellation, the exporter still validated revision 2.
The fix checks cancellation before each retained-row validation and before each
candle revision group. Cancellation raises before publication or stage creation.
It does not promise interruption within one bounded canonicalization/sort call.

Ten additional disposable SQLite cases reseal an altered second store while
holding its configured identity fixed. Source/snapshot/epoch/schema changes,
missing completeness/availability/revision claims, either lagging watermark,
and missing routing all fail closed. Recomputing a content seal cannot override
the independently configured source contract.

Validation used only the existing financial venv and fresh task-owned SQLite
fixtures. The focused RED run was one failure with
`cancelled export continued validating retained revisions`; GREEN was 11 passed.
The regression selection covers exporter, native catalog, producer readiness,
and snapshot contracts, excluding PostgreSQL tests and external signer tests.
No working database, external node, native OS probe, service, workflow, or node
manifest was accessed or changed. No native history or producer epoch was invented.

Final regression command (existing venv Python):

```text
-m pytest tests/research/test_financial_grid_exporter.py tests/research/test_grid_source_capabilities.py tests/research/test_grid_producer_readiness.py tests/research/test_financial_snapshot.py -q -k "not postgres and not signer and not sign_retry" --basetemp=../grid-contract-final-20261026
58 passed, 40 deselected in 42.30s
```

`git diff --check` passed. The default pytest temp directory was inaccessible;
a fresh explicit task-owned base was used without changing ACLs or deleting
preexisting data. PostgreSQL and signer execution are intentionally unverified
by this cycle; the selection does not assert those results.
