# Mechanism mapping on the integrated candidate

Reference source: google-deepmind/alphafold `c77e5d2a8961d1a353632c462914ff0a32a950f6`, modules.py. Current implementation is an independently authored financial adaptation. Local/reference test success does not certify complete upstream AlphaFold equivalence. No biological weights or atom structures are used as financial outputs.

| Original mechanism | Financial adaptation / implementation | Reference / acceptance test | Remaining limitation |
|---|---|---|---|
| MSA row attention with pair bias | historical aligned tracks; alphafold_msa_attention.py, connected via financial_structural_model.py | test_alphafold_msa_attention.py; connected hooks/gradients and unavailable-value perturbation | One forecast origin per call; not per-position streaming parity |
| MSA column attention | same-time exchange across instrument tracks; build_column_attention | explicit per-track/head loop oracle; masks and connected gradients | Financial track meaning is declared, not biological MSA equivalence |
| MSA transition | normalized residual MLP in StructuralLayer | connected gradient/mask tests | Dropout/training schedule differs from original protein model |
| Outer product mean | mask-count normalized track-to-pair update; alphafold_outer_product.py | explicit double-precision outer-product oracle; track/parameter/byte admission | Strict finite CPU tensors and bounded dimensions |
| Triangle multiplication outgoing/incoming | learned gated pair contractions; alphafold_triangle.py | explicit-index incoming/outgoing contractions; budget/mask tests | Full independent upstream parameter/equation transfer not certified |
| Triangle attention starting/ending | pair-edge attention; alphafold_triangle_attention.py | orientation transpose/gradient oracle and explicit attention checks | Selected adaptation; complete upstream parity gate BLOCKED |
| Pair transition | normalized residual transition inside alphafold_pair_stack.py | pair-stack mask, gradient and workspace boundary tests | Conservative caps can reject otherwise computable configurations |
| MSA/single/pair exchange | OPM into pair, pair bias into row, target track extraction into single | all required operator hooks called; target-track permutation changes forecast | Track zero must be the explicitly named target instrument |
| Recycling | shared learned stack over bounded repeated MSA/pair representations | invocation count, changed output, mask invariance through recycles | Does not recycle protein positions or biological atom geometry |
| Residual connections | row/column/MSA/pair and recycling residual paths | finite active-parameter gradients and connected output tests | No claim of original dropout or parameter initialization schedule |
| Normalization/masking | LayerNorm; binary availability mask zeroed before projections | all-masked/invalid-mask cases; future perturbation invariance | CPU float32/float64 computation only; half/GPU rejected before projection |
| Numerical stability | bounded scale, stable log differences, normalized attention | Decimal return oracle, literal variance, extreme-price and finite-gradient tests | No mixed-precision/CUDA stability evidence |
| Financial output | Gaussian mu/scale for checkpoint-bound horizon; typed Prediction | horizon mismatch, wrong SHA, modified weights, availability/schema tests | Exploratory distribution; real-data calibration/OOS remains BLOCKED |

Training: actual optimizer updates, deterministic seed, fresh-process verified tensor-JSON reload, cancellation rollback, chronological purge, multi-instrument/timeframe fixtures, strict context+label instrument holdout. Neural walk-forward creates a fresh model per disjoint test window; prior OOS reuse requires explicit sequential-retraining policy and never yields an independent/pooled portfolio claim. Split, costs, holdout, steps and model configuration are retained in experiment reports.

Data: normalized read-only SQLite WAL concurrency is tested. Actual legacy candle DDL without historical knowledge/provenance/coherence is rejected. Multi-source Grid/PostgreSQL/SQLite atomicity and historical availability cannot be reconstructed and remain externally BLOCKED until verified producer exports exist.
