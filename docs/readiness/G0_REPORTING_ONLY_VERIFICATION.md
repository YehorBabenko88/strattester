# G0 v2 reporting-only verification

Base: `593cf92b1cfbfb6a04961dd7f260349c01459cc0` from the refreshed PR21
integration branch. This change contains documentation, declarative schemas,
ordinary unit tests, a development-only jsonschema dependency and a reporting
workflow. No collector, qualification, capture, trust, admission or other
`strattester` runtime source is changed. The blocked implementation is not
resumed or imported.

## What was checked

Collector schema1 / observation contract2 and manifest version1 are distinct.
Tests cover five manifest states across all ten groups, exact required fields,
unknown versions/booleans, non-authorizing envelopes, receipt-field membership,
missing/null/empty/partial data and mocked PowerShell5.1/7 outputs. Both schema
files use internal references only. Neither executes or opens declared commands
or evidence locations.

Initial RED: missing schema file (one failure); this proves the missing
declarative deliverable, not a collector defect. First GREEN:130 passed.
An additional draft-schema boundary test produced10 failures/1 pass: wildcard
annotations allowed unknown null receipt fields. Explicit per-group property
membership fixed it:11 passed/130 deselected. The existing runtime already
rejects unknown receipt fields; it was not changed.

Final focused suite: **267 passed,0 skipped**,46.39seconds on Python3.12,
pytest9.1.1,jsonschema4.26.0. Command:

```text
python -m pytest tests/test_g0_reporting_schemas.py tests/test_physical_g0_inventory_contract.py tests/research/test_g0_evidence_inspection.py tests/research/test_parallel_g0_preflight.py -q --basetemp=<new-task-owned-directory> --junitxml=<evidence.xml> --json-report --json-report-file=<evidence.json>
```

The fresh reviewer ran74 schema/reporting tests,56 deliberately deselected,
without duplicating mocked PowerShell runs; no actionable findings in that
review snapshot. The subsequent receipt-field boundary correction above has
its own RED/GREEN and complete focused regression evidence.

The dedicated `g0-reporting-only` workflow selects the same four files on hosted
Windows, requires both shells,267 passes and zero skips/deselections, then binds
JUnit/raw JSON/log hashes to checkout HEAD. Actual run status/URLs and final
source SHA are recorded externally after publication to avoid self-hash cycles.
No full-repository or physical-qualification success is claimed here.

## Findings and limits

- P0: no new confirmed issue in this reporting scope.
- P1: physical G0 remains blocked: owner-selected VM, independent identity,
  receipts and all ten fact groups are uncollected. Existing blocking is retained.
- P2: draft-schema unknown-field issue corrected; JSON Schema's mathematical
  integer semantics, byte limits, duplicate-key checks and strict parsed runtime
  types remain distinct. Mocked compatibility does not qualify OS providers.

Target selection remains NOT_SELECTED. All ten physical groups remain
NOT_COLLECTED/null, PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED,
G1_EXECUTE/CLEANUP=NOT_AUTHORIZED,DEPLOYMENT/TRADING=NO-GO,
GRID_NATIVE_HISTORY=BLOCKED. No physical LS5/PC4, production DB/service,
privilege, network-policy, protected-launch or G1 operation was performed.
