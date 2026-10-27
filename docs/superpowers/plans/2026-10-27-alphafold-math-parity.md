# AlphaFold / financial parity audit plan

**Goal:** Audit PR21's refreshed source, add independent references, and deliver a Draft PR on parallel/alphafold-math-parity.

**Architecture:** Tests derive small CPU equations in NumPy/Decimal, observing only input tensors and mapped parameter arrays. Preserve version-two financial adaptation semantics and document differences from pinned AlphaFold and Grid/math contracts.

**Constraints:** No main merge, G1, trading, production data or GPU execution. Base is refreshed PR21 HEAD f60869686a51693799b4844a1af49c9b39ba45d5. Dedicated disposable clone provides isolation.

## Tasks
- [ ] Review pinned upstream MSA/pair/triangle/recycling source and financial ingestion/label/evaluation paths.
- [ ] Extend `tests/research/test_structural_upstream_differential.py` with a complete small NumPy trunk oracle; compare recycling 0/1/2, masks, batch and depth, input and selected parameter derivatives.
- [ ] Add `tests/research/test_financial_math_parity.py`: exact integer time, Decimal returns and population/sample distinction, actual financial target horizon and availability guards.
- [ ] Prove references detect deliberate equation/recycling defects without leaving production mutations.
- [ ] Register exact nodes in `scripts/financial-gate-manifest.json`, so existing exact-HEAD hosted gates execute the new tests.
- [ ] Run focused baseline, reference tests and full safe software suite; record all failures/skips.
- [ ] Produce source comparison and P0/P1/P2 report, SHA256 evidence, push branch and create Draft PR against PR21 integration branch; inspect exact-HEAD CI and preserve acceptance blockers.

## Review focus
Asymmetric/empty masks; zero pair counts; gradients through recurrent state; population versus sample volatility; extreme finite prices; integer nanosecond horizons and availability boundaries. Full biological inference and physical Grid history remain separate unverified requirements.

## Execution decisions
User authorized end-to-end audit/tests/Draft PR; proceed inline. Test-only oracle extensions do not require production equation changes. Do not copy implementation from the math repository. A test PASS establishes finite-domain equation agreement only.
