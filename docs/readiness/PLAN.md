# System readiness / read-only G0 execution plan

Authority: owner request 2026-10-24 and QA comment 6386645500. Baseline
67301726d250973602b964adabdb9eb8d50d0f13, integration branch only.

1. Pin PR15–21 refs, compare updated source deltas, inspect CI; preserve baseline evidence.
2. Independently audit actual runtime/data/math/security; distinguish reproduced failures from missing evidence.
3. Reproduce acceptance bypasses RED, fix fail-closed; reproduce filesystem publication failures RED and fix within existing offline artifact scope.
4. Specify producer-issued coherent export and independently test consumer contract. Never fabricate producer facts or connect to production DBs.
5. Read-only local G0 inventory and command/operation/network/resource/STOP/cleanup manifest. Unknown remote hosts remain BLOCKED. Owner signature remains pending.
6. Run bounded existing/new tests, update pinned CI nodes, commit/push isolated PR21 changes, capture exact-HEAD hosted evidence.
7. Independent review and final readiness statuses. G1 remains NOT_AUTHORIZED.

Pre-flight: producer contract feeds snapshot consumer, not runtime DB open. Acceptance consumes pinned test manifests, never a report's own requirements. G0 inventory cannot authorize G1. No automatic architecture expansion to a production execution route.

Ledger:
- Baseline verified clean, PR21 draft at67301726; source17/18/19/20 advanced; no bulk import.
- Acceptance RED: six failures reproduced; corrected suite23 passed. Evidence work/g0-acceptance-{red,green}.log.
- Independent system/model/security reviewers audit baseline read-only. Existing local venv only, no installation.
- Ruling: incomplete registry wiring remains an explicit readiness blocker; silently wiring research to mutable stores would exceed a read-only prephysical audit and is unsafe without trusted producer data.
- Ruling: external gates are permanently BLOCKED in current aggregator until a real trusted verifier is implemented; caller status strings have no authority.
- Artifact RED:3fail2pass (hardlink, staged-byte mismatch, deep root); GREEN19pass. Exact evidence work/g0-artifact-{red,green}.log. Windows hostile-directory confinement and abrupt-crash recovery remain OPEN.
- Export specification reference14pass; test-side HMAC fixture only, no native producer claim.
- Full precommit suite801pass4explicit skips18subtests; pinned manifest814nodes. G0 collector readonly LS5 captured, initial missing nullable service StartType normalized; inventory output contains no command lines/DSNs/secrets.

- Final reviewer reproduced introduced cleanup TOCTOU; RED1fail5pass; removed failed-final unlink entirely. GREEN20pass, independently repeated20pass. Reviewed full suite802pass4skip18subtests; manifest815nodes with new regression.
- Reviewed updated source CI: PR18 math andPR20 collection FAIL on absent PR21-only modules; no source-branch mutation.
