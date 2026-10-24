# MATHEMATICAL_SYSTEM_READINESS

Status: bounded offline mathematical verification; system acceptance BLOCKED.

Verified test-code SHA: `45f9fca96871b8a70af2bbcffe9a022b3695aaf4`.
Baseline: `f35be5fbc915b528319610105acbcc9982ba55bb`.
Runtime: Windows CPU, Python 3.12.10, NumPy 2.5.4, torch 2.14.1+cpu.
No dependencies installed, production services accessed, or upstream math parity asserted.

## Evidence

New suite: **33 passed, zero skipped**. Combined selected contract/oracle suite:
**83 passed, 4 subtests passed, zero skipped**. The 33 new tests import NumPy
and torch directly; missing CPU dependencies fail collection.

Run from repository root using the existing sibling virtual environment:

```powershell
../financial-venv/Scripts/python.exe -m pytest tests/research/test_financial_mathematical_verification.py -q
../financial-venv/Scripts/python.exe -m pytest tests/research/test_financial_mathematical_verification.py research/test_independent_decimal_oracles.py research/test_independent_time_oracles.py research/test_math_contract_reference.py tests/research/test_financial_contract.py tests/research/test_financial_evaluation.py tests/test_alphafold_training_independent_oracles.py -q
```

## Actual implementation coverage

- Exact explicit ns/ms conversions through integers above float64's exact-integer
  range; oracle rejects fractional milliseconds. Units are declared, never inferred.
- Actual `feature_tracks` against 70-digit Decimal log returns, rolling means,
  and population volatility including its initial zero return and eight-token
  window. Tiny/large positive prices and constant prices are covered. Export is
  intentionally float32; comparisons allow float32 rounding. Five numeraire
  transformations check scale invariance.
- Actual ledger distinguishes a 100% simple cash return from log(2).
- Actual Gaussian scoring against Decimal closed form, translation and unit
  transformations, scale Jacobian and coverage invariance. Large-offset Decimal
  comparisons allow binary cancellation; they are not exact float/Decimal parity.
- Actual outer-product pair operator against independent scalar NumPy loops,
  independently evaluated population LayerNorm, learned affine weights, pairwise
  joint-track counts, zero-count masking, and repeated-track invariance. Float64
  tolerance is 2e-12. Seeds 0, 7, 29 are deterministic finite-domain properties.
- Prediction integer horizon validation plus inference rejection of untrained,
  misaligned and unit-mismatched horizons before checkpoint/model access.
- Train-only z-score Decimal comparison and test-set perturbation apply to the
  **reference helper only**. The executed feature pipeline uses raw return/moment
  channels and does not invoke that helper. No executed train-scaler parity claimed.

## Severity and limits

**P0:** none found within these exercised boundaries. This is not evidence that
the complete model, strategy, data producer or operating system has no P0 issue.

**P1:** baseline `gaussian_scores([1e308], [1.], [-1e308])` returns infinite NLL
and MAE despite finite inputs. Extremely small scales can also overflow. Reported
to the training/evaluation owner, who reproduced and is adding fail-closed guards
and regression tests. This branch intentionally changes tests/docs only; the
owner's fix must be integrated and verified before claiming this issue closed.

**P2:** no full finite-domain proof, Hypothesis fuzzing, GPU parity, biological
AlphaFold parity, or production acceptance. The actual sibling math repository
contains a README only, so no numerical implementation is available for a true
cross-repository comparison. Independent references are explicitly identified.
No claims of profitable performance or calibrated predictive uncertainty follow
from formula agreement. Incoming triangle attention correction belongs to its
operator owner and is outside this branch's baseline evidence.

Timestamp integers are unbounded by this Python contract; this verifies arithmetic,
not external database int64 admission. Equal-looking wrong-unit integers cannot
be detected without trusted provenance. Full acceptance remains BLOCKED pending
the system's external evidence and integration gates.
