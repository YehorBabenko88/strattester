# UPSTREAM_MECHANISM_READINESS — cycle4 final independent conclusion

**Audit source HEAD:** `eaf6b819ae7da2b72ce984040842ca711480212d`
**Integration baseline:** `4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7`
**Pinned AlphaFold upstream:** `c77e5d2a8961d1a353632c462914ff0a32a950f6`
**Result: TRIANGLE_ORACLE_PASS / FULL_EVOFORMER_EQUIVALENCE_NOT_PROVEN / SYSTEM_NO_GO.**

## Direct pinned upstream equation review
The pinned `alphafold/model/modules.py` source explicitly uses outgoing `ikc,jkc->ijc` and incoming `kjc,kic->ijc`. The financial triangle contraction matches these index orientations. This does not establish equivalence of weight initialization, gating, normalization, masking, training or whole-model behavior.

## Exact-head observed evidence
- Independent [cycle4-upstream-triangle run 40359780431](https://github.com/YehorBabenko88/strattester/actions/runs/40359780431): **13 PASS, 0 skipped**, strict accounting SUCCESS, CPU torch 2.14.1. Log-reported artifact ZIP SHA256 `ea49bad86be6bfa2752c604c9091f7783c9aadc386de66dd09d450189d1184ec`. Original ZIP was not independently downloaded/rehashed.
- [Main tests 40359780306](https://github.com/YehorBabenko88/strattester/actions/runs/40359780306): workflow SUCCESS.
- [Financial 40359780275](https://github.com/YehorBabenko88/strattester/actions/runs/40359780275): eight engineering jobs SUCCESS; system-acceptance-NO-GO FAILURE. This is not financial system readiness.

## Classification
| Mechanism | Result |
|---|---|
| MSA row/column attention and pair bias | ADAPTED; independent full-upstream parity not established |
| MSA transition and outer product mean | ADAPTED; OPM projection/normalization order differs |
| Outgoing/incoming triangle multiplication | INDEX EQUATIONS VERIFIED; otherwise ADAPTED |
| Starting/ending triangle attention | ADAPTED; full pinned parameter parity not established |
| Pair transition, single/pair representations, residual normalization | ADAPTED |
| Recycling | ADAPTED; original stop-gradient and first-row behavior differ |
| Financial Gaussian distribution head | ADAPTED; real OOS calibration unproven |
| Protein IPA/structure/atom/confidence heads | NOT IMPLEMENTED |
| Faithful full AlphaFold Evoformer | NOT VERIFIED |

## Findings and disposition
- **P0 BLOCKED:** historical Grid producer availability/revisions/coherent cut, real OOS, GPU, physical G1, whole-upstream equivalence.
- **P1 VERIFIED IN SCOPE:** two triangle orientations, CPU float32/float64 scalar reference, finite-difference gradients, all-masked and finite-large inputs, nonfinite admission, bounded tensor resource check.
- **P1 OPEN:** full independent NumPy parity for row/column, OPM, triangle attention, pair transition and recycling on current integration HEAD; cross-timeframe causal isolation; trained forecast calibration.
- **P2 OPEN:** explicit multi-timeframe fusion and versioned non-Gaussian research heads.

**Decision:** independent triangle acceptance COMPLETE; independent *whole-Evoformer* acceptance INCOMPLETE. Keep Draft/NO-GO. No merge, trading, production DB mutation or G1 authorization.
