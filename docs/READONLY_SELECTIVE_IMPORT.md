# Selective read-only import disposition

Integration baseline: `33fd4dcf5dd1f7c16130567f0b24915931d8595d`.
Target: `integration/alphafold-financial-system`. This is a new blocked read-only
boundary, not a fix for a demonstrated baseline defect.

## Pinned sources and imported objects

PR #42 (`codex/workstream-a-readonly-results`), source HEAD
`ef1c53861998188bdd03b9f037dc45573b3c2acb`, tree
`f7d3fd6ebeb0a53bd840274c12c03c6ca224ffb4`. Source review used its
changed-file delta against `37ff`, not a branch replacement of integration.
The following files were imported unchanged:

| File | Source blob |
| --- | --- |
| `strattester/readonly_api.py` | `d99e01f8d0917032530bae0f1b07141a837fa07e` |
| `tests/test_readonly_api.py` | `ba0698475a7812b6a4ed1bf56f08f737a7a3a3b3` |
| `docs/READONLY_RESULTS_API.md` | `8076567c93893899ab2d1adc29e3e85630c8b1af` |

PR #43 (`codex/provenance-a`), source HEAD
`943095d00d5d56276f3832c42b36b290bea77a84`, tree
`5b9d99f3beb55ba31ea551ef9c1c82488c6f457a`. Review used the changed-file
delta against PR #42 HEAD. No #43 producer or admission code is imported.

| Reviewed file | Source blob | Disposition |
| --- | --- | --- |
| `research/provenance.py` | `2b7e46a46310aa53e1afc077b84d098f15455ed4` | Defer producer and validator together |
| `research/runner.py` | `34e558193a5d15145a32fb7cb0f90fae9ec33704` | Preserve baseline runner |
| `research/result_persistence.py` | `9c8439478aed6a7e6ac4691725eef526d4045667` | Preserve current report contract |
| `persistence/result_store.py` | `c4d9ad9ac6f7f1ff63583a2c3769c2c2876cf8ae` | No owned_runs schema/trigger mutations |
| `readonly_api.py` | `b908b098a88e3b31f6b31e40fa7e24e8b651208e` | Keep blocked #42 implementation |

Reviewed paths in the last table are relative to `strattester/`.

## Contracts and reasons for deferral

The actual executor returns `StrategyResult.output`, an arbitrary strategy
output object. Existing scientific persistence derives metrics from
`report.primary`, and fenced persistence stages/promotes with job ID, lease
token and node generation. PR #43's `execute_owned` labels raw strategy output
as metrics and its optional runner route does not establish that report/fence
binding. Its default lease validator always succeeds and cancellation defaults
to false. These are source inspection findings, not claims that the baseline
financial runner failed a test.

The proposed `FrozenDatasets.entries` exposes mutable row and object containers;
its read methods ignore requested start/end windows. Its declared source
identity/revision/model assumptions are caller arguments, rather than evidence
derived from the admitted financial runner/session. External receipt admission
would still require a real owner policy. The #43 read route uses SQLite
`mode=ro` without the immutable metadata-only constraint and therefore does not
share #42's no-sidecar access contract. A producer redesign must bind exact
financial report, immutable input/source identity, cancellation and publication
authority before any result capability is enabled.

Current boundary contract: no configured trust mechanism; every results route
returns unavailable and discloses no records. Capabilities advertise all result
features false. Only explicit application calls perform a metadata-only
`mode=ro&immutable=1` probe; no listener, service, workers, network operations,
database creation or source schema mutation is introduced. WAL freshness is
deliberately unqualified. No production database or physical inventory was used.

## Independent verification

Tests authored before production import:
`tests/test_readonly_import_boundary.py`. RED command:

```text
..\financial-venv\Scripts\python.exe -m pytest tests/test_readonly_import_boundary.py -xq --tb=short --basetemp=.pytest-readonly-red
```

Result: one failure on absent `strattester.readonly_api` (new capability RED).
An earlier default-temp attempt hit Windows temp-directory permissions; the
workspace-local `--basetemp` resolved the test harness issue.

GREEN command:

```text
..\financial-venv\Scripts\python.exe -m pytest tests/test_readonly_import_boundary.py tests/test_readonly_api.py tests/research/test_runner.py -q --tb=short --basetemp=.pytest-readonly-green
```

Result: **27 passed**. Independent cases cover tampered and self-rehashed
receipts, source mismatch, COMPLETE/RUNNING/ABORTED/FAILED/CANCELLED rows,
default empty admission, byte/directory preservation, missing source and parent
noncreation, bounded queries, forbidden methods and path traversal. They test
the blocked boundary; they do not claim to validate an unimported producer's
execution, failure or cancellation lifecycle. Financial runner, financial owner
signatures, native blocked stage, funding, Grid and root G0 files are unchanged.
