# Final training source audit — PR23

Audit target: PR23 `parallel/alphafold-training-backtest-pr21-integration`, actual local and GitHub head `1dcd46a500e74bedd730cdc77c9b761511b0a082`. Root comparison `5d715987d03d4a26d31a48e9767697bbd171cd33`; merge base `67301726d250973602b964adabdb9eb8d50d0f13`. No root/source branch edits, installations, physical G1, production database, services or main merge were performed. Only this report is persisted; CPU probes used disposable synthetic fixtures in a temporary sibling directory and existing financial-venv.

## Decision

Do not wholesale import PR23. Its genuinely new dispatcher/spec/strategy adapter duplicate the stronger root signed offline inference/registry path and are incomplete. Retain root ownership of executable dispatch. The independent oracle file is already byte-identical in root; no import needed. The source's four independent oracle regression tests are useful, pass against root, and may be selectively imported as tests only.

## Dependency and ownership matrix

| Source path | Exact source blob | Existing root owner/dependency | Recommendation |
|---|---|---|---|
| `research/alphafold_training/independent_oracles.py` | `1d5f7e85a9f084ebab98244861f2da546294cc45` | Same blob already in root; `tests/test_alphafold_training_independent_oracles.py` covers it | No import; avoid duplicate alias/module |
| `strattester/research/financial_research_spec.py` | `48b5963eacea32020ec38976fb2a407b9edefa73` | Depends on Instrument/integer; overlaps ExportPolicy/AttestedInferenceRequest and experiment budgets | Do not add second runtime contract; integrate desired universe restriction into canonical policy only with a reviewed change |
| `strattester/research/financial_research_dispatch.py` | `575f8e7054f437e191d09b40b17fb6f323fb1508` | Calls root load_checkpoint and predict_snapshot; bypasses financial_attested_inference.run_attested_offline | Reject as runtime import |
| `strattester/strategies/builtin/alphafold_financial.py` | `b23a502707da82e9c4e939365e0c37399fe157e3` | Duplicates conceptual FINANCIAL_STRUCTURAL_RESEARCH adapter/explicit registry | Reject duplicate; source adapter always blocks and has no registered caller |
| `tests/research/test_financial_independent_oracles.py` | `fb9ba63e409b5b555afbec67b82724fadc4643e7` | evaluate_ledger, gaussian_scores, existing oracle | Safe test-only import; four tests locally pass |
| `tests/research/test_financial_research_spec.py` | `995d9570d21fbfa2b1d8b84c1f37f433168c015f` | New spec only | Do not import absent spec |
| `tests/research/test_financial_research_dispatch.py` | `7a90067fcd53016f4fb41bc4f4e5d93687f840b6` | New dispatcher only; mostly mock boundary rejection tests | Do not import wholesale; one supplied test errors |
| `tests/strategies/test_alphafold_financial.py` | `323f32432e02b5542972bf8945e272927aeb3c7a` | New adapter only | No runtime justification |

## Reproduced findings

1. **Raw unsigned Snapshot bypasses root attestation and stale forecast boundary.** The new dispatcher accepts an ordinary in-memory `Snapshot` whose `VERIFIED`/producer fields are caller assertions; it never calls `load_attested_export`, signature verification, a trust store, policy cutoff, cancellation or aggregate job memory admission. An exact source-module overlay on root, with a two-token one-track synthetic CPU model (`model_equations_version=2`) and real digest-pinned JSON checkpoint, successfully predicted from producer `unsigned-fixture`, origin 120, horizon 300 and available_ns 999999. A completely arbitrary nonempty model_version also passed. This demonstrates missing contracts, not a live/production exploit: root's existing signed route remains intact unless this duplicate is wired in.
2. **Every concrete pathlib Path is rejected.** Line42 uses `type(model_path) not in (str, Path)`; `Path('checkpoint.json')` has type `WindowsPath` here (and `PosixPath` on POSIX). The valid bounded checkpoint above is accepted as str and rejected as Path with `checkpoint path must be a nonempty ordinary filesystem path`. Use of `isinstance` or explicit accepted concrete types would need review if retaining code.
3. **Supplied regression test fails before its purported assertion.** `test_malformed_checkpoint_metadata_rejected` constructs FakeSnapshot without `bars`; dispatcher line29 raises AttributeError, not expected ValueError, before load_checkpoint or metadata validation. Exact supplied four test modules loaded from source Git objects against root: 30 tests, 29 pass, 1 error, no fixture/database/network used.
4. **Resource gates are weaker than canonical admission.** max_tracks/max_tokens checks happen after `load_checkpoint` constructs model tensors; max_samples/max_folds are never consumed by dispatcher; model_version is never matched against metadata. Root loader still validates equation version and its config/parameter budgets; root feature_tracks validates actual alignment and feature allocation. These inherited controls limit the duplicate's scope but do not replace aggregate input/model admission in run_attested_offline.

## Runtime reachability and compatibility

Root's canonical flow is explicit register_financial_research -> execute_financial_research -> FinancialStructuralResearch.run_context -> run_attested_offline -> load_attested_export/signature policy -> bounded config/aggregate admission -> load_checkpoint -> predict_snapshot. It uses FINANCIAL_STRUCTURAL_RESEARCH version0.2.0 and feature versions signed_snapshot_v1/financial_equations_v2.

Source ALPHAFOLD_FINANCIAL_RESEARCH version0.1.0 uses financial_structural_v1 and declares a legacy candle requirement but its run_context always raises, even when definition is enabled manually. No source caller/registry wiring is supplied in the delta. It is an intentionally dead adapter/stub, not an additional usable research strategy. Its definition has a distinct ID, so this is semantic duplication rather than a literal ID collision.

Source dispatch itself is callable when explicitly imported; ordinary source StrategyContext does not reach it. Merely importing would not auto-enable trading. Its functions are compatible with root signatures for load_checkpoint and predict_snapshot and inherited equation-v2 loader checks, as the real-checkpoint probe confirms. Compatibility with signed authorization is absent by construction: neither dispatch argument list nor spec has signature/trust/policy inputs.

The oracle `reference_interval_overlap` test only exercises the oracle against constants; it is not a regression against production interval exclusion. The long/short/flat oracle now passes `-position * funding_bps /10000` as signed unit-long funding so multiplying by position yields the canonical nonnegative charge for either direction. This is consistent with evaluate_ledger's documented flat per-horizon funding cost, not evidence of exchange funding-schedule simulation. Gaussian test uses only mu0/sigma1/y0. reference_calibration is not exercised by the new integration file (existing root tests do exercise it).

## Actual hosted evidence

Read-only `gh pr view 23` confirms head `1dcd46a500e74bedd730cdc77c9b761511b0a082` on the named branch. `gh run view 40123208705 --json headSha,conclusion` reports that exact head and failure. Logs reproduce the same malformed metadata fixture error in all four OS/Python jobs:

- Ubuntu 3.11: 1 failed, 806 passed, 3 skipped, 29 subtests passed.
- Ubuntu 3.13: 1 failed, 806 passed, 3 skipped, 29 subtests passed.
- Windows 3.11/3.13: 1 failed, 807 passed, 2 skipped, 29 subtests passed.

Run https://github.com/YehorBabenko88/strattester/actions/runs/40123208705 . Another pytest run40123203656 also fails per PR checks. Run40123208738 is also exact source head and overall failure: training, core, CPU, data, integration, math and security checks pass, while system-acceptance-NO-GO fails. Passing narrow training checks do not establish a green PR or physical G1 authorization. No failure cause beyond the inspected pytest logs is inferred.

## Meaningful tests before any adapted import

- Preserve canonical signed-export end-to-end tests, including forged/expired/untrusted/replayed manifests and valid signature path.
- Use a real typed two-token Snapshot plus real bounded equation-v2 checkpoint in successful canonical offline inference; assert provenance and NO-GO marker.
- Assert availability before origin and outside forecast horizon reject before checkpoint model allocation.
- Assert aggregate serialized inputs plus model work budget reject before tensor construction; retain root equation-v1/missing-version checkpoint rejection and config admission tests.
- If a policy universe restriction is adopted, test unauthorized target and context instrument/timeframe on real typed fixtures before loading model bytes.
- Add valid concrete WindowsPath/PosixPath acceptance and arbitrary path-object rejection if filesystem-path validation is changed.
- Broaden ledger oracle cases to independently selected positive/negative signed funding and explicit canonical flat-charge conversion; compare production interval exclusion against oracle at boundary/overlap cases; test nontrivial Gaussian means/scales/labels.

No approval, owner signature or VM controls are assumed. Physical G1 remains unauthorized without the separately required signed owner authorization and VM controls.
