# UPSTREAM_MECHANISM_READINESS — cycle4 independent audit

**Status: DRAFT / NO-GO.** Integration source HEAD `4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7`, tree `5e8862ab22aa51055f96022c428b2d90f8b5abc2`. Pinned original: `google-deepmind/alphafold@c77e5d2a8961d1a353632c462914ff0a32a950f6`.

## Direct source comparison
Read original `alphafold/model/modules.py` lines 1380–1468 at pinned SHA. Upstream uses outgoing `ikc,jkc->ijc` and incoming `kjc,kic->ijc`. PR21's current `alphafold_triangle.py` uses matching index orientations. Its gate initialization and mask/output conventions are adaptations, not parameter-by-parameter upstream equivalence.

## Mechanism classification
| Mechanism | Classification |
|---|---|
| MSA row attention with pair bias, column attention, MSA transition | ADAPTED |
| Outer product mean | ADAPTED (normalization/count ordering differs) |
| Triangle multiplication outgoing/incoming | ADAPTED (index orientation matches pinned source) |
| Triangle attention starting/ending | ADAPTED |
| Pair transition, single/pair representation, residual and normalization | ADAPTED |
| Recycling | ADAPTED (differentiable financial recycling, not upstream stop-gradient behavior) |
| Gaussian forecast head | FINANCIAL ADAPTATION, no real OOS calibration |
| Protein IPA, atom structure module and biological confidence heads | NOT IMPLEMENTED |
| Full faithful AlphaFold runtime | NOT VERIFIED |

## Verified integration boundaries
`financial_pipeline.predict_snapshot` selects one explicit timeframe, verifies model checkpoint identity and horizon, moves target to track zero, and calls `model(x,mask)`. StructuralLayer invokes row, column, MSA transition, OPM and pair stack; pair stack invokes both triangle orientations and pair transition. Only one forecast origin is supported; intermediate positions are not independently causal predictions. Multiple instruments are aligned exactly. Multi-timeframe fusion is not implemented by this function.

## New differential checks
`test_cycle4_upstream_triangle_oracle.py`: 4 orientation/dtype scalar-reference cases, 2 all-masked output/gradient cases, 1 resource ceiling case. Independent explicit loops avoid reproducing the subject's einsum contraction. Dedicated CPU CI requires seven distinct PASS results. **New tests are committed but not yet executed at authoring time.**

## P0
- Grid historical availability/revisions/coherent epochs remain externally blocked.
- Real market OOS, physical G1, full native launcher and GPU remain blocked.
- No claim of full upstream parity; pinned upstream runtime not executed.

## P1
- Check CI exact audit HEAD and preserve JSON/JUnit/ZIP SHA256 evidence.
- Extend independent NumPy forward/gradient oracles for row/column, OPM, triangle attention and recycling against the current candidate.
- Adversarial extreme-value and multiple timeframe contamination tests, including no use of unavailable context.
- Validate training/checkpoint provenance and Gaussian calibration on untouched real OOS before claiming predictive utility.

## P2
- Versioned alternative distribution heads and cross-timeframe fusion need separate design and compatibility review.

No merge, live orders, production DB mutations, or unauthorized G1.
