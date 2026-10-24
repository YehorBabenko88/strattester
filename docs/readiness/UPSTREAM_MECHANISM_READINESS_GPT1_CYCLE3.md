# UPSTREAM_MECHANISM_READINESS — GPT-1 cycle3

Status: **NO-GO / independent tests pending**.

Source: integration PR21 exact HEAD `5d715987d03d4a26d31a48e9767697bbd171cd33`. Upstream mechanism reference: `google-deepmind/alphafold@c77e5d2a8961d1a353632c462914ff0a32a950f6`. No original runtime or pretrained protein weights used.

## Mechanism matrix
| Mechanism | Classification |
|---|---|
| MSA row attention + pair bias | ADAPTED |
| MSA column attention | ADAPTED |
| MSA transition | ADAPTED |
| Outer product mean | ADAPTED |
| Triangle outgoing/incoming multiplication | ADAPTED (incoming corrected under equations v2) |
| Triangle starting/ending attention | ADAPTED |
| Pair transition | ADAPTED |
| Recycling | ADAPTED |
| Single/pair representations, residual, normalization, masks | ADAPTED |
| Protein IPA structure module, atomic geometry, pLDDT/PAE heads | NOT IMPLEMENTED |
| Faithful upstream-equivalent full AlphaFold | NOT VERIFIED |
| Financial Gaussian head | ADAPTED; not calibrated real OOS |

## Evidence and call graph
`financial_pipeline.predict_snapshot` checks model fingerprint and horizon, constructs time-aligned tracks, moves the named target to track 0, then calls `model(x,mask)`. `financial_structural_model.StructuralLayer` calls row attention, column attention, MSA transition, OPM and pair stack (triangle multiplication/attention, pair transition); bounded recycling repeats the layers. This is one-origin inference, **not** a valid per-position streaming forecast.

PR21's reported hosted engineering gates at 40118594284: 994 pass, 0 skip; system acceptance BLOCKED intentionally. Those counts are PR21-provided evidence, not independently downloaded/recomputed in this cycle. The new ten metamorphic cases and dedicated workflow have not yet executed at authoring time.

## P0
- Producer-issued Grid coherence, historical availability and revisions remain unverified; do not infer from synthetic snapshots.
- No real-market OOS, registered GPU proof or authorized physical G1.
- A disposable CPU checkpoint must be trained and exported only in a controlled test environment with immutable source/dataset/config fingerprint; none is fabricated or bundled here.

## P1
- Verify target-fixed context permutation invariance, unavailable context perturbation, deterministic inference and active finite gradients across recycle counts 0/1/2; ten new tests cover these conditions.
- Independently compare float64 forward and finite-difference gradients against pinned upstream NumPy reference with parameter translation before claiming faithful.
- Stress large finite values, all-masked contexts and resource ceilings in isolated workers.

## P2
- Multi-timeframe features currently select one explicit timeframe per model call; cross-timeframe fusion is not equivalent to multi-timeframe ingestion.
- Gaussian scale is an uncalibrated research distribution; alternative heads need separately versioned output schema and checkpoint contracts.
- Apache-2.0 attribution applies to any copied upstream source; no upstream code copied in this cycle.

No merge, DB writes, trading, production services, or model deployment.
