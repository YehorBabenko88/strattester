# G0 acceptance cycle implementation plan

**Goal:** complete safe pre-acceptance preparation on baseline 9c913494481abbfc997e1c0a9dd46fab04576ebb.
**Spec:** docs/readiness/NEXT_CYCLE_G0_ACCEPTANCE.md.
**Execution:** continuous implementation authorized by the owner; no repeated architecture approval.
**Architecture:** preserve research-only fail-closed boundaries; measure code in disposable fixtures, never active LS5/PC4. Independent reviews and selective source imports retain exact provenance.
**Tech stack:** Python, PowerShell, existing CPU environment and hosted GitHub Actions.

## Constraints and review focus

G1 NOT_AUTHORIZED; trading NO-GO; no main merge, active-host inventory, production databases, service controls, or resumed blocked native work. Missing evidence is BLOCKED. Review missing versus empty observations, private-data redaction, immutable artifact identity, funding units/market scope, and historical claims unsupported by producer facts.

## Tasks

- [x] Refresh HEAD/comments/related Draft PRs and pin source identities.
- [ ] Test read-only G0 script through mocked commands only: UDP ownership, GPU driver metadata, missing-observation status and legacy PowerShell hashing. Add only demonstrated corrections; preserve native guarantees as unproven.
- [ ] Independently review authenticated funding intake using bounded exact identity, Decimal rates and external trust. Import only independently verified changes with source/blob provenance.
- [ ] Verify Grid schema/producer facts and OOS prerequisites; reject incompatible/stale source changes rather than manufacturing history.
- [ ] Run local relevant/full regression and exact-node collection; update gate manifests for admitted tests.
- [ ] Obtain independent security/math review; preserve RED and GREEN evidence.
- [ ] Push minimal commits to PR21, inspect exact-HEAD hosted reports/artifacts and retain all skips/deselections.
- [ ] Publish G0/readiness and owner-signable disposable G1 plan with STOP/cleanup, exact source/tree, artifact digests and external blockers.

## Source integration rulings

PR37's corrected dataset loop now equals the integration baseline. Its new expectations ending at times[-2] contradict the actual last legal target times[-1]; do not import those expectations. PR35's HMAC/float helper is not a drop-in replacement for producer Ed25519/Decimal contracts; inspect/adapt rather than merging the branch.
