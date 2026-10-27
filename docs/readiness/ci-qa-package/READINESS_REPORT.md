# Exact-source qualification readiness — 2026-10-27

Source PR #21 HEAD refreshed through GitHub and origin before audit: `f60869686a51693799b4844a1af49c9b39ba45d5`.
Tree `0f7626787ec835a9a945a8e576d19181044f23ec`. Audit branch `parallel/ci-qa-package`.
This report qualifies that source commit; documentation commits on this branch are separate and do not inherit its CI results.

## Decision

Software mandatory gates PASS; system acceptance BLOCKED. Physical G0 NOT_COLLECTED; G1 execute/cleanup NOT_AUTHORIZED; deployment/trading NO-GO. No native binary, G1, trading, physical collector, target VM, database or protected host operation executed locally. Hosted native component evidence is reviewed only.

## Independently downloaded evidence

Four exact-head workflow runs; 18 job logs; nine ZIPs with API digest matching SHA256 and verified ZIP CRC. API run head and artifact head bind source. Raw JSON, normalized node IDs and JUnit multisets agree for all 1556 distinct mandatory parent tests. Parameter text is preserved literally. Subtest assertions are not counted as additional parents. Gates: core 594, data 185, math 146, cpu 141, training 66, security 336, integration 88; zero mandatory skips/errors/failures/deselections.

| Run | Result | Scope |
|---|---|---|
| [40548912536](https://github.com/YehorBabenko88/strattester/actions/runs/40548912536) | FAILURE | Seven software gates pass; acceptance BLOCKED/exit 2, failed=[] |
| [40548912336](https://github.com/YehorBabenko88/strattester/actions/runs/40548912336) | SUCCESS | Windows/Linux, Python 3.11/3.13 |
| [40548912423](https://github.com/YehorBabenko88/strattester/actions/runs/40548912423) | SUCCESS | Four reference jobs, 12 passed each |
| [40548912498](https://github.com/YehorBabenko88/strattester/actions/runs/40548912498) | SUCCESS | CPU 76 passed, 2 deselected |

Windows full suite: each 1502 passed, 21 skipped, 21 subtests passed. Linux: each 1476 passed, 47 skipped, 21 subtests passed; Python 3.13 retains 3 warnings. All skip lines and reasons remain in raw logs; these are not zero-skip qualification. Full/reference/CPU runs have no published result artifacts; their accounting is log evidence, unlike mandatory gates. No new workflow was dispatched by this audit.

## Native and integrity

Native source hashes independently match git blobs at the source commit. Hosted build manifest records two equal builds with pinned compiler/reference/BouncyCastle package digests. Actual extracted executable SHA256 is `a8420da78900865c7fb061e9bfaf5104d15f72d3fbd62c21ce534f5db8c7a6f5`, matching diagnose and build manifest. Native tests: 30 parents and 4 subtests; receipts retain native_enforcement=false and research_process_created=false. This is COMPONENTS_ONLY, not full isolation. DNS service proxy, filesystem confinement, execution bridge, qualified research transport and output bounds remain missing.

## Acceptance bypass and local tests

Fresh isolated pytest environment, Python 3.15 on Windows: `python -m pytest tests/research/test_financial_acceptance.py tests/research/test_physical_acceptance_attacks.py -q --basetemp=../test-temp-explicit --junitxml=../evidence/local-acceptance.xml --json-report --json-report-file=../evidence/local-acceptance.json`: 23 passed. This is a focused local check, not a full dependency/runtime qualification. Initial attempt 21 passed/2 temp ACL setup errors is retained separately. `pip check` passes for the QA-only environment.

Attack cases cover stale SHA, skipped/failed/error/xfail/xpass/deselected accounting, wrong node sets, reduced gates, cancelled jobs, boolean schema and forged external PASS. Aggregation loads repository manifest and permanently blocks seven physical/external requirements even when caller claims PASS. No admission bypass demonstrated. JSON artifact authenticity itself remains UNVERIFIED_SELF_REPORT; SHA256 proves bytes, not trusted physical facts or owner authority.

## Reproducibility and dependencies

Existing prepare_windows_offline_package.py produced two unequal archive hashes with identical member bytes: `530d02413c7bb528e1352f535e8ef5a3477da07d009567c051dadf7639b1ea72` versus `00b5d9e4772d7d4ddd0441347fd264ee38dd202ffb9f1a7d3c5431b85af657ed`. Wall-clock ZIP timestamps prevent byte reproducibility. The delivery archive built for this audit uses sorted entries, fixed timestamps/permissions and ZIP_STORED, and two independent builds must match. This does not claim reproducible wheels or offline dependency installation.

pyproject uses ranged requests/psutil/tzdata, dev/postgres dependencies and setuptools; Torch is exactly pinned. Main Python workflows install from indexes without a complete transitive hash lock and use action version tags; native workflow pins action commits and toolchain package hashes. No vulnerability-free claim, fresh full runtime install, wheelhouse reconstruction or cross-machine package reproduction is established. Existing claimed 160 MB qualification ZIP was not available as a tracked asset or Actions artifact in this audit; its stated hash is not revalidated.

## Findings

| Priority | Finding | Disposition |
|---|---|---|
| P0 | No newly demonstrated acceptance bypass | No claim of absence of all vulnerabilities |
| P1 | PR #21 description claims native SHA256 18f579c8…; exact-head artifact/diagnose/build instead agree on a8420da7… | Use full measured digest above; owner must reconcile stale published evidence before signing |
| P1 | Native components do not enforce a full sandbox; physical identity, authority, paths, snapshot/rollback and private delivery missing | BLOCKED; no G1 authorization |
| P1 | Python dependency closure lacks committed immutable hash lock/wheelhouse | Reproducible offline runtime not established |
| P1 | External grid coherence, real OOS, GPU, upstream parity, physical G0 and owner G1 evidence unavailable | Acceptance remains BLOCKED |
| P2 | Existing offline ZIP builder uses wall-clock timestamps | Reproduced; deterministic audit ZIP supplied without modifying production builder |
| P2 | Full-suite skips, CPU deselections, Linux warnings; initial local temp ACL errors | Preserved, never promoted to executed PASS |

## Owner signing

Use existing TARGET_G0_* templates and the companion OWNER_REVIEW template. All unknown target facts, signer IDs, keys, nonce and times remain null; no signatures fabricated. This is a review template, not an executable authorization or canonical receipt. Package SHA is supplied externally to avoid a hash cycle. A completed declaration cannot clear implemented fail-closed admission by itself.
