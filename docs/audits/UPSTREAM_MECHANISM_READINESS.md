# UPSTREAM_MECHANISM_READINESS — independent audit (2026-10-24)

**Verdict: NO-GO / PARTIAL / upstream parity NOT VERIFIED.**

## Pinned evidence
- Reviewed PR #21 source at exact HEAD `67301726d250973602b964adabdb9eb8d50d0f13` (Draft).
- Upstream reference requested: `google-deepmind/alphafold@c77e5d2a8961d1a353632c462914ff0a32a950f6`. This audit uses the documented upstream mechanism identities and PR21's own mechanism matrix; direct upstream source retrieval was unavailable in this session. **Do not claim bytewise source or numerical upstream parity.**
- Files read directly at exact SHA: `financial_structural_model.py`, `financial_pipeline.py`, `alphafold_msa_attention.py`, `alphafold_outer_product.py`, `alphafold_triangle.py`, `alphafold_triangle_attention.py`, `alphafold_pair_stack.py`, existing structural tests and mechanism matrix.
- PR21 reports 789/0 engineering tests at workflow 40109884642, but reported CI counts/artifact attestations have not been independently revalidated here.
- This audit's new reference tests are committed but **not yet executed or CI-certified**.

## Mechanism classification
| Mechanism | Classification | Reason |
|---|---|---|
| MSA row attention and pair bias | ADAPTED | Financial tracks, optional causal mask, no biological MSA; connected in StructuralLayer |
| MSA column attention | ADAPTED | Attention over instruments at fixed time; independent double-precision oracle added |
| Outer product mean | ADAPTED | Mask-count normalized OPM; independent loop oracle added |
| Triangle multiplication outgoing/incoming | ADAPTED | Both gated contractions present; independent loop oracle added |
| Triangle attention starting/ending | ADAPTED | Both directions and pair bias; complete upstream parity not established |
| Pair transition | ADAPTED | Residual normalized MLP |
| Recycling | ADAPTED | Shared repeated stack; no biological structure recycling |
| Normalization/masks | ADAPTED | LayerNorm and binary availability; does not establish per-position causality |
| Protein structure module / IPA / torsion/atom heads | NOT IMPLEMENTED | Financial Gaussian head instead |
| Faithful complete Evoformer | NOT VERIFIED | No pinned-upstream differential parameter transplant |
| Forecast output | ADAPTED | `predict_snapshot` uses target-first track order and returns typed Gaussian mu/scale, checkpoint-bound horizon |

**FAITHFUL** denotes numerically equivalent to pinned upstream under matched parameters; **none certified**.

## P0
1. **Historical per-position causal semantics are not guaranteed.** `FinancialStructuralModel.forward` performs unrestricted within-origin pair and column/row exchange, and calls `self.row(msa,pair,mask)` with default `causal=False`. This is consistent with **one forecast at the latest available origin**, but unsafe if intermediate token representations are reused as historical per-token forecasts. Add an explicit one-origin-only contract and adversarial tests proving no historical outputs are exposed.
2. **Missing producer-issued availability proof** for multi-source Grid/SQLite/PostgreSQL coherence, as already blocked in PR21. No real deployment or trading.

## P1
1. Target/context permutation is intentionally **not invariant** when target changes. With the same named target and permuted contexts, the forecast should be invariant within tolerance; require metamorphic test through `predict_snapshot` and fresh-process checkpoint.
2. Masked intermediate operators may produce finite outputs on zero mask; confirm zero output and zero gradients under fully masked inputs for every module and every recycling iteration.
3. Extreme finite inputs (e.g., near floating-point overflow) pass input-finiteness checks but may overflow intermediate projections/contractions. Add output-finiteness gates and fuzz adversarial magnitudes before artifact publication.
4. Check actual CUDA admission, peak memory and cancellation independently; CPU-only evidence cannot certify GPU.

## P2
1. Distinguish checkpoint's positive scale from calibrated volatility; a softplus scale is not automatically predictive or calibrated.
2. Audit numerical tolerances across CPU float32/float64 and repeated recycle counts.
3. Preserve Apache-2.0 notices if copying upstream source. Current financial operators are independently written.

## Acceptance
- Added `research/upstream_mechanism_reference.py` and `tests/research/test_upstream_mechanism_differential.py` with independent explicit-index OPM, triangle, column attention oracles.
- Required next: run exact-HEAD CPU gate and archive JUnit/JSON/SHA, then adversarial masks/permutations/extremes, inspect upstream pinned source independently, check forecast integration, GPU and real OOS.
- No merge, orders, model deployment, or database mutation authorized.
