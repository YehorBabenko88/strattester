# G0 v2 reporting-only verification plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify existing G0 observation reporting and provide non-executable review materials.
**Architecture:** Declarative JSON schemas and ordinary tests only; existing collector and admission code unchanged.
**Tech Stack:** JSON Schema 2020-12, pytest, mocked PowerShell 5.1/7.
**Spec:** User's restricted work order and docs/readiness/G0_OBSERVATION_CONTRACT_V2.md.

## Global constraints

No resumption/import of blocked qualification implementation. No process privilege,
network-policy or protected-launch changes. No physical collector invocation,
LS5/PC4 operations, production DB/services, G1, trading or main merge.
Ten unobserved groups remain NOT_COLLECTED/null; software tests never imply PASS.

## Review focus

- Provider NOT_COLLECTED is invalid; manifest NOT_COLLECTED is a template sentinel.
- Schema1 and observation contract2 are separate integers, not booleans.
- Missing/null facts cannot become successful empty lists.
- EMPTY listeners do not establish network isolation or target acceptance.
- PS5.1 and7 mocks replace all inventory calls; no escalation or fallback.

## Tasks

- [x] Add failing schema-presence/validation tests in tests/test_g0_reporting_schemas.py.
- [x] Add static schemas for existing collector and evidence manifest in docs/readiness/schemas; rerun tests.
- [x] Verify PS5.1/7 mocked report shapes and absence/error state semantics with schema tests.
- [x] Add read-only owner-selected VM checklist and ten-group final-report template, leaving target identity unset.
- [ ] Run focused unit regression, diff check and exact-head CI; publish Draft PR and SHA256 evidence.
- [ ] Hand off exact HEAD/CI/results and limitations to the main Codex chat Stratt.

## Ledger

- Base refreshed to 593cf92b1cfbfb6a04961dd7f260349c01459cc0. Remote requested branch did not exist; created it locally in a fresh clone.
- User explicitly restricted scope; prior blocked work is neither resumed nor imported.
- Reuse existing fully mocked collector harness. Add no physical command or new runner.
- jsonschema test dependency installed only into task-owned work/reporting-deps; existing interpreter environment unchanged.
- New schema tests: 130 passed before boundary additions. Schema-only fresh review: 74 passed/56 deselected; PowerShell deliberately excluded by reviewer.
- Final boundary check found unknown *_sha256 fields admitted through unevaluatedProperties annotations. Ten RED tests failed; explicit per-group additionalProperties=false fixed the draft schema; 11 GREEN/130 deselected. No runtime defect or qualification fix is claimed.
- Final focused suite: 267 passed/0 skipped in 46.39s. Collector and all strattester runtime files unchanged against base.
- Ruling: run the reporting-only suite, not unrelated native/DB/physical launch suites — this user explicitly restricted work to ordinary reporting verification. Hosted baseline workflows may trigger automatically on the PR; they are not manually dispatched by this task.
