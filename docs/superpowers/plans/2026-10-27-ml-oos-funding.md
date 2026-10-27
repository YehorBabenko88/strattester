# ML OOS funding implementation plan

Goal: finish the existing offline research design on parallel/ml-oos-funding.
Spec: ../specs/2026-10-24-alphafold-integration-design.md, training/evaluation section.
Execution: inline, within the user's explicit implementation and Draft PR request.

Architecture: retain fresh models per purged fold and synthetic-only signed sessions.
Fit a bounded Gaussian scale multiplier using validation only; retain raw scores.
Connect separately pinned funding through an explicit optional bundle, retaining
signature/history distinctions. Add itemized independent round-trip accounting.
Recovery is deterministic restart, not optimizer continuation: classify pinned
checkpoint artifacts without modifying or adopting orphan files.

Constraints: no main merge, G1, trading, production DB, real-data invention,
automatic funding admission, pickle, or relaxation of external acceptance gates.

Review focus: future labels changing calibration; timeframe/market funding alias;
missing funding coverage including flat trades; late-fold failure/retry; modified
checkpoint and untrusted recovery digest.

- [x] Write RED tests for validation calibration, cost rows, signed funding join,
  recovery verification and multi-fold failure/restart.
- [x] Implement calibration and ledger; preserve raw replay and existing APIs.
- [x] Implement explicit funding bundle pins and synthetic session join.
- [x] Implement bounded read-only recovery inspection; test fresh deterministic retry.
- [ ] Run CPU E2E with multi-instrument/timeframe holdout, baselines, controls,
  calibrated scores, authenticated synthetic funding, checkpoint replay and hashes.
- [ ] Add real OOS protocol and exact-HEAD CI; run full tests, review, push Draft PR.

Review: independent read-only reviewer reproduced three P2 findings, each fixed
with RED-to-GREEN tests: held-out validation calibration, absent funded control
ledgers and fresh-process inference gap. Full-suite packaged-runtime test exposed
a missing calibration dependency; runtime allowlist extended, revalidation pending.

Design choice: extend the existing structural research harness rather than build
a second trainer or import deferred PR43. Existing contracts and test oracles
remain authoritative. Real OOS stays BLOCKED pending independently qualified
historical data, labels, funding, controls, and registered one-use evaluation.
