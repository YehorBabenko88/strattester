# UPSTREAM_MECHANISM_READINESS

Verdict: **bounded CPU equation regressions PASS; full upstream equivalence NOT PROVEN; physical/GPU/model acceptance BLOCKED**.

Baseline: `f35be5fbc915b528319610105acbcc9982ba55bb`. Tested implementation commit: `704afb090a60bb44fab1e6e4c8a08cee08d13ace` on `cycle2/structural-model`. Reference checkout: AlphaFold `c77e5d2a8961d1a353632c462914ff0a32a950f6`. Implementation began only after coordinator confirmed baseline hosted workflows completed and artifacts were checked (financial run 40115330224: seven engineering jobs, 815 pass/0 skip; acceptance remains BLOCKED).

## Actual prediction path and source comparison

`financial_structural_model.forward` projects available feature tracks, then invokes row attention, column attention, MSA transition, outer-product mean, outgoing/incoming triangle multiplication, starting/ending triangle attention and pair transition. Shared layers repeat `recycles+1` times, then the target track's last available token and a masked pair mean feed the distribution head. Thus these are exercised prediction operators, not disconnected reference utilities. Forecasting is at one available origin; this is not a per-token causal streaming network.

| Mechanism | Pinned upstream source | Result and limits |
|---|---|---|
| Row attention | `modules.py` Attention 579–692, MSARowAttentionWithPairBias 795–855 | Independent NumPy normalization, projection mapping, scalar attention and gating agree on dense/asymmetric/empty and finite-large inputs. Head/input finite differences agree. |
| Column attention | `modules.py` MSAColumnAttention 858–912 | Track-axis attention agrees with independent scalar NumPy reference. Added finite-input admission before normalization. |
| Triangle attention | `modules.py` TriangleAttention 963–1034 | Independent calculation for both orientations, rather than starting-module-as-ending-oracle, agrees on asymmetric masks and pair-derived query/key-vertex bias. |
| Triangle multiplication | `modules.py` 1384–1465 and `config.py` incoming equation at 294 | Reproduced incoming projection-orientation defect; corrected `left[k,i]*right[k,j]` to upstream `left[k,j]*right[k,i]`. Independent NumPy normalization/projections/contraction/output covers both directions. |
| Recycling and head | `modules.py` get_prev 332–338 and embedding recycling 1958–1972 | Independent NumPy boundary-state recurrence and final masked pooling/head checks pass for 0/1/2 recycles. Layer outputs are observed inputs to this recurrence oracle; it is **not** an independent whole-network oracle. |

## Reproductions and compatibility

The new differential file first produced **5 failed, 23 passed** against unmodified production code: incoming triangle equation (asymmetric three-vertex fixture), column NaN/+Inf/-Inf admission, and legacy checkpoint missing equation version allocating a model. Unsupported explicit version cases already rejected baseline and are not counted as newly found defects. Red evidence: `evidence/structural-cycle2/red.log` and `red.xml`. The old triangle reference reproduced the implementation's reversed contraction; its expectation was corrected alongside the independent oracle.

`StructuralConfig.model_equations_version=2` now binds corrected semantics to checkpoint identity. Checkpoint loading requires the field before constructing the model and validates exact integer version 2. Legacy checkpoint configs missing the field, version 1, and boolean versions are rejected before parameter allocation. No automatic migration is provided. Existing weights trained with reversed incoming equations require an explicit separately reviewed migration or retraining; adding a version field to old weights does not establish equivalent predictions. Fresh version-2 save/reload and fresh-process prediction tests pass. The standalone column fix is a lower-level admission correction; the financial model already rejected nonfinite features, so no prediction-boundary leakage is claimed.

## Verification

Existing environment only: Python 3.12, torch `2.14.1+cpu`, NumPy `2.5.4`; CUDA unavailable. No installation, GPU run, production data access, service launch or G1 operation.

From this worktree, PowerShell:

```powershell
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
../financial-venv/Scripts/python.exe -m pytest -q tests/research/test_structural_upstream_differential.py tests/research/test_alphafold_triangle_reference.py tests/research/test_financial_structural_model.py tests/research/test_financial_checkpoint.py --basetemp=work/cycle2-model-green-temp --junitxml=work/cycle2-model-evidence/green.xml
../financial-venv/Scripts/python.exe -m pytest -q --basetemp=work/cycle2-model-full-temp --junitxml=work/cycle2-model-evidence/full.xml --json-report --json-report-file=work/cycle2-model-evidence/full.json
```

Scoped GREEN: **59 passed, 0 skipped** in 7.37s, including **28 new cases**. Full default suite console: **855 passed, 4 skipped, 18 subtests passed** in 26.06s; no failures/errors. JUnit includes subtest records and reports 877 test records, 4 skips. Its four explicit skips are two CUDA-unavailable checks and two Windows symlink-unavailable checks; none is a numerical pass. Raw console/JUnit records are retained in `evidence/structural-cycle2/`. The new file is not yet in the coordinator-owned pinned gate manifest; coordinator must regenerate inventory before claiming gate inclusion.

Independent attention tests use only parameter arrays from the subject: NumPy manually computes normalization, affine mappings, scalar dot products, stable softmax and sigmoid. No subject normalization/projection/operator is reused to calculate expected values. Gradients use central finite differences of that NumPy calculation. These fixtures are tiny (one batch, three tracks/vertices, four channels/two heads) in float64, with finite-large scaling 1e6; they are not exhaustive or a numerical guarantee at floating-point maxima. Existing prediction admission tests exercise shape/workspace/operator-cap rejection before projection and unsupported float16; per-forward budgets do not establish whole-job or concurrent-job memory confinement.

## Deliberate adaptations and remaining blockers

Upstream is not executed: no JAX/Haiku installation or upstream pretrained weights were used. Source-equation references cannot prove whole AlphaFold numerical equivalence. PyTorch random initialization, financial features/head and CPU admission differ. Our stricter query masks and explicit zero treatment for empty groups differ from upstream's key-mask softmax policy. Outer-product mean divides the contraction by clamped counts before the output projection; upstream applies projection then divides by counts plus 1e-3. Recycling reuses every financial track and remains differentiable; upstream recycles only the first MSA row and stops gradients between iterations. These were documented, not silently changed. No biological structure module/IPA, templates, position recycling, full Evoformer dimensions/dropout or biological inference is supplied.

Real GPU parity, physical hardware acceptance, attested historical data, market OOS/calibration/cost acceptance and production/runtime confinement remain separate unmet requirements. No profitability, GPU, full-upstream-equivalence or G1 PASS is granted.
