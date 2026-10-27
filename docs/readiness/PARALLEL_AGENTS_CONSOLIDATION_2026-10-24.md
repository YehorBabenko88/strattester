# Parallel agents consolidation — 2026-10-24

## Baseline
PR #21 previous pinned HEAD: e0d09edb8be934463d4cbd884bdddac76ca50f1e.
All changes are committed to the same Draft PR; no merge to main and no live G1.

## Imported without modifying source branches
- PR #17 eab45b5d9ce04f8282755684a1c1e93b03e38c77:
  strattester/alphafold_export_receipt.py, tests/test_alphafold_export_receipt.py,
  docs/GRID_DATA_PHYSICAL_READINESS.md.
- PR #18 afeab9e8e71d5ebc0114cd0ed693db613a86fbcd:
  research/independent_decimal_oracles.py, research/independent_time_oracles.py,
  research/test_independent_decimal_oracles.py, research/test_independent_time_oracles.py.
- PR #19 24045ec1035c34f13e3b70c1c13dff2cb789ef34:
  research/alphafold_training/independent_oracles.py,
  tests/test_alphafold_training_independent_oracles.py,
  research/alphafold_training/ML_AND_STRATEGY_ENGINE_READINESS.md.
- PR #20 2c5e378777112b9152e42cf2261f29ef8d29bf13:
  docs/security/pr21-independent-physical-g1-assessment-20261024.md.

## Deliberate omission
PR #20 tests/research/test_pr21_acceptance_bypass_characterization.py
is an intentionally RED characterization of the *old* acceptance bypass:
it asserts the insecure result == PASS and pins stale 67301726.
Its behavior is invalid on the hardened integration HEAD; do not copy or
quietly xfail it. Existing PR #21 GREEN rejection regressions supersede it.
Keep it as historical evidence in PR #20 only.

## Integration constraints
The Grid export receipt verifier requires external trustworthy signature callback.
It does NOT provide producer authenticity, real historical availability or a
cross-store coherent export. Imported reference oracles have not been wired
into production paths; these provide independent tests only. Runtime/registry
bridge and strict-offline environment are still absent.

## Acceptance
Previous exact-HEAD 815 passed/0 skipped applies only to e0d09ed.
All incoming commits invalidate that exact-HEAD result for the new candidate.
Record hosted CI and test node accounting on the new final HEAD.
Acceptance BLOCKED; G0 PARTIAL/UNSIGNED; physical G1 DENY/NO-GO.
