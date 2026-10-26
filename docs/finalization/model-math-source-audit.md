# Final model/math source integration audit

Read-only source review against root `5d715987d03d4a26d31a48e9767697bbd171cd33`, 2026-10-26. No root/source edits, installations, GPU, database/service actions, branch changes or merges. Disposable source copies and reports only were written under work/final-model-math-probes. Evidence is integration suitability, not financial predictive validity or G1 approval.

## Recommendation

Import reviewed PR29 test files; retain equations version 2 and root production code. Repair report verifier identity coverage and workflow triggers before treating it as a mandatory gate. Do not cherry-pick PR22 or PR18 wholesale. PR22 contains a reproduced obsolete incoming-triangle equation. PR18 would weaken an existing production differential test and introduces a reproducibly failing precision assertion. Preserve root files on collisions.

## Ownership and dependency boundaries

* PR29 HEAD `36dbe30a032245a491244eb3a0390dae2edcafd1` mergebase is root HEAD. Its 11-file delta is tests, report verifier, workflow and readiness documentation; zero production model changes. Torch is optional via importorskip in tests; exact CPU workflow installs torch 2.14.1, pytest and pytest-json-report. Existing financial-venv is Python 3.12.10 / torch 2.14.1+cpu.
* PR22 HEAD `bea8f3009a21b4db1b222b03e7769a185ae11e86`, mergebase `67301726d250973602b964adabdb9eb8d50d0f13`. Three-operator reference module uses torch arithmetic and production normalization/projection modules in expected values. It is an index oracle, weaker independence than root NumPy equations oracle. Do not represent it as original AlphaFold inference.
* PR18 HEAD `0ce06f5a021e9261ba9a2f060906133bbe11690d`, mergebase `37ff7e9d12a4d2dccd788fc493c28557dbe8bcea`. Its 44-file own delta is research reference math/oracles/tests/contracts/workflow. Most new tests compare reference helpers with other reference equations; passing does not establish production integration. No production imports of these new oracle modules were found. Keep them test-only, with explicit production differential adapters before claiming coverage of ingestion, training or financial metrics.
* Pinned sibling AlphaFold verified HEAD `c77e5d2a8961d1a353632c462914ff0a32a950f6`; config.py incoming equation is `kjc,kic->ijc`. Root financial_structural_model StructuralConfig explicitly requires model_equations_version=2; root incoming triangle uses left[k,j]*right[k,i]. Root tests/research/test_structural_upstream_differential.py supplies NumPy normalization/projection/softmax equations and legacy checkpoint rejection; preserve it.
* Sibling math README is a browser mathematical laboratory, not a Python numeric dependency; README states no default license. No source import from that repository is recommended or needed.

## Reproduced findings

1. Combined PR29 and PR22 tests on root: **58 passed, 1 failed**, 5.11 seconds, bounded CPU threads. PR22 test_triangle_differential_masked_double[True] mismatched 16/36 entries, max absolute 0.7309321872184287. Its helper uses left[k,i]*right[k,j], contradicting pinned upstream and root equations-v2. Repair helper incoming indexing AND corresponding mask coordinates; use asymmetric mask and distinct projection weights, then cross-check with root NumPy oracle. Do not change production to satisfy stale oracle.
2. PR18 research tests on root: **80 passed, 1 failed, 4 subtests passed**, 1.22 seconds. test_target_horizon_and_availability compares a precision-70 Decimal result against default precision-28 Decimal arithmetic. Repair expected expression inside localcontext precision 70 (or define explicit quantization/tolerance). This is a test precision defect; horizon calculation's financial correctness is not disproven by it.
3. PR18 research/test_independent_decimal_oracles.py replaces root gaussian_scores(...) with a handwritten formula, removing actual production differential coverage. Keep root version. Its research/test_math_contract_reference.py changes qualified import to unqualified math_contract_reference; keep root version to avoid path-dependent imports. Five changed-source paths already byte-identical with root (listed below); no import needed.
4. PR29 report verifier accepts a synthetic report with 38 unique fabricated test names spread across the seven required file basenames. It checks count and filenames, not exact node identities despite workflow label. Reproduced with final-model-math-probes/fabricated-report.json. Add checked-in full expected nodeid set, enforce equality, and test substitution of a valid node by fabricated identity. It is a local report accounting verifier, not authenticity attestation.

## Missing coverage and required integration adaptations

* PR29 connectivity checks hooks fired and finite input gradients, not nonzero per-operator parameter gradients or causal contribution. A disconnected/zeroed branch could still satisfy hook counts. Add selected operator ablations or parameter-gradient sensitivity tests if claiming all operators affect forecast.
* Optimizer/reload smoke test demonstrates any parameter changes and tensor-state exact reload in memory; it does not test real checkpoint metadata/schema, all trainable parameters, durable serialization, optimizer resume, dataset correctness or empirical performance. Keep root actual checkpoint version tests.
* PR29 workflow pull_request paths only include its tests/script/workflow. It will not run on later production operator/model changes. PR22 and PR18 workflows have similar test/reference-centric paths. Add relevant strattester/research production paths and root integration workflow registration. Reject skips via explicit dependency preflight/report accounting; optional importorskip alone is insufficient.
* PR18 gradient oracle tests analytical Gaussian derivative against finite differences of a local formula, not model loss/autograd. PR29 checks only three input coordinates for each recycle 0/1; useful smoke coverage, not a full Jacobian proof.
* PR22 new oracle module is test-support-only, not a runtime fallback. Prefer root independent NumPy reference as authoritative equations-v2 oracle; PR22 adversarial tests can be selectively retained, deduplicating invariants against PR29/root.
* No GPU, JAX/Haiku inference, pretrained biological weights, production DB, network training, deployment, G1 or real-data financial validation was performed.

## Exact CI metadata

Captured read-only with gh pr view --json headRefOid,statusCheckRollup,url; raw response in final-model-math-probes/ci.json. Check rollup reflects listed PR HEAD, not root-combined candidate and not necessarily exact-head workflow event checkout provenance. Do not promote these checks to combined integration proof.

* https://github.com/YehorBabenko88/strattester/pull/29, HEAD `36dbe30a032245a491244eb3a0390dae2edcafd1`: {'SUCCESS': 16, 'FAILURE': 1}.
  * system-acceptance-NO-GO: FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40122097176/job/120958042579

* https://github.com/YehorBabenko88/strattester/pull/22, HEAD `bea8f3009a21b4db1b222b03e7769a185ae11e86`: {'SUCCESS': 16, 'FAILURE': 1}.
  * system-acceptance-NO-GO: FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40112056135/job/120927621239

* https://github.com/YehorBabenko88/strattester/pull/18, HEAD `0ce06f5a021e9261ba9a2f060906133bbe11690d`: {'FAILURE': 4, 'SUCCESS': 8}.
  * reference (ubuntu-latest, 3.11): FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40123276839/job/120959238717
  * reference (ubuntu-latest, 3.13): FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40123276839/job/120959238815
  * reference (windows-latest, 3.11): FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40123276839/job/120959238585
  * reference (windows-latest, 3.13): FAILURE, https://github.com/YehorBabenko88/strattester/actions/runs/40123276839/job/120959238867

PR29 structural dedicated cpu check succeeded; PR22 independent check succeeded on its own older model base. PR18 all four dedicated reference jobs failed. Failure causes of hosted jobs have not been independently retrieved here; local horizon failure is reproduced, but hosted attribution remains unverified. Both PR29/22 have system-acceptance-NO-GO failure; no claim of complete CI success is warranted.

## Reviewed source import manifest

Blob hashes are git blob SHA-1, pinned at source HEAD, not file SHA-256. This manifest describes safe review disposition, not authorization to overwrite root. PR29 tests are accepted on current root by the combined run; failures belong to PR22. Documentation needs freshness edits and must not be imported as verified readiness evidence.

| Source | Path | Blob | Disposition |
|---|---|---|---|
| alphafold-structural-gpt1-cycle3 | `.github/workflows/cycle3-structural-invariants.yml` | `3fb312da8dad5a9799e80045c9acbe9f84f96b15` | ADAPT production triggers |
| alphafold-structural-gpt1-cycle3 | `docs/readiness/UPSTREAM_MECHANISM_READINESS_GPT1_CYCLE3.md` | `4973c03b34ee6e63132c0f192e3548b1cc04dcf3` | REVIEW stale readiness narrative |
| alphafold-structural-gpt1-cycle3 | `scripts/cycle3_structural_report_gate.py` | `7a0407aec2b9f91ef97b5d1bc3d46d64a2532347` | ADAPT gate exact nodeids |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_checkpoint_readiness.py` | `018065be56a6be226ab60e947a9aae857d02a226` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_cpu_contract.py` | `c9abac5ebc37edb020585c6930f6c3f511f7d77c` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_forecast_contract.py` | `f24a0de442d9c283b416e38d28f0d1a05030bb4f` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_gradient_oracle.py` | `ab6e9b890293f3d912f6d5750e3e39bafcf2e3c9` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_operator_connectivity.py` | `46036414b8c7bcd1ea0dc1709e7337e2ad3b6bd8` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_report_gate.py` | `61f9d970be2a0f1369d63576ad595495b26fbfcb` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_resource_admission.py` | `960ea928a5a7e896b9c3af7b004008f628753651` | IMPORT test |
| alphafold-structural-gpt1-cycle3 | `tests/research/test_cycle3_structural_invariants.py` | `f51c47695083787757a6e36fb05e46fd47317482` | IMPORT test |
| alphafold-upstream-mechanism-20261024 | `.github/workflows/upstream-mechanism-independent.yml` | `14f8f23934d1a81295f2dde1b9a13b5744aa3cd2` | ADAPT workflow / readiness narrative |
| alphafold-upstream-mechanism-20261024 | `docs/audits/UPSTREAM_MECHANISM_READINESS.md` | `0f0cd94da670da0ff00e0b588d877fd085d68e36` | ADAPT workflow / readiness narrative |
| alphafold-upstream-mechanism-20261024 | `research/upstream_mechanism_reference.py` | `62ba98dff671be26b3723d69e39239b3bb246a8c` | REPAIR incoming equation before import |
| alphafold-upstream-mechanism-20261024 | `tests/research/test_upstream_mechanism_differential.py` | `0494bcc8e64af169b5a1fff375ea901063c33b4c` | REPAIR incoming equation before import |
| alphafold-upstream-mechanism-20261024 | `tests/research/test_upstream_structural_adversarial.py` | `8e5c69c7ae616af0aaf6db85bc4f44f7c3e6c0d6` | IMPORT optional adversarial tests; deduplicate |
| alphafold-grid-math | `.github/workflows/mathematical-contract-reference.yml` | `b89436eac07bf885aa3142a7a38af5ec42c4e974` | ADAPT paths and production differential registration |
| alphafold-grid-math | `docs/MATHEMATICAL_SYSTEM_READINESS.md` | `1fc345ea583911ce30914c55eff4d049ab0eb059` | REVIEW documentation; no readiness promotion |
| alphafold-grid-math | `docs/contracts/grid_strattester_ml_math_v0.1.md` | `73a51aeff8510edd7c82f41239699d6785f89742` | SKIP: root identical |
| alphafold-grid-math | `research/independent_asof_revisions.py` | `838c9e68ac7139d24611eb351c71112da769b2ee` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_candle_boundaries.py` | `a2404c8378800d0f752455b51b9ef30273b348d9` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_decimal_oracles.py` | `8c17fc574ea885bcd4b8b858e51b95f9f0a3444b` | SKIP: root identical |
| alphafold-grid-math | `research/independent_dependency_oracle.py` | `868091ee183de638486128bc98e0974f9abb1521` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_event_clock.py` | `a7d6104074978728649477d066af1fa2a12d6d5e` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_gaussian_stability.py` | `cfd2d545a5a3d61be06c8ffba9d5915e4acfa6f5` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_gradient_oracles.py` | `1c79c2a1ca2dfc068f0457310cd9f7e6d8b348d8` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_horizon_oracle.py` | `9595f7f2f7f6c04b531e42662983f3026af2cfe5` | HOLD pair until Decimal expectation repaired |
| alphafold-grid-math | `research/independent_ledger_oracle.py` | `156e353cfe4ea8caebe343b374a87b2384f40d39` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_normalization_oracle.py` | `c4e14279ebed031419187b685b6f5a36480a35ac` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_numpy_oracles.py` | `23e7b6fa741b2b2d350dfba776ee9ccebd35e11e` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_precision_oracle.py` | `2c183c2b0f676019bf47854eb2d06da4fea1739e` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_provenance_oracle.py` | `ada872e791b9f605808ef21bb03889f2fd56a35c` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_purge_oracle.py` | `b9c5b187130e5d20a6abfdf965623fb8e030329d` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_series_identity.py` | `fdf00d20e7735fd4d4eaafcde09c75ed65c79e81` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_snapshot_integrity.py` | `99922e248564f8086c6577bcd10f561c216be9bd` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_time_oracles.py` | `398730a3415036819295b8601f0d0efa853b2242` | SKIP: root identical |
| alphafold-grid-math | `research/independent_timestamp_units.py` | `7190338e2ae9682c8337d65d142c456b45126735` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/independent_watermark_oracle.py` | `f67ef6454cfaae047e4d3c3e062c49b17f204251` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/math_contract_reference.py` | `ce14ddff7bbce725bc61c4e962babfcb681569d0` | SKIP: root identical |
| alphafold-grid-math | `research/test_independent_asof_revisions.py` | `92e3890c01903faa4baa61bc48b1913917ee68cc` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_candle_boundaries.py` | `6f4706d624a31a0081f8bde89537c79b2e72f61d` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_decimal_oracles.py` | `f6dd72e67eb31ab853dea4407247d57ac8279dff` | KEEP ROOT: source weakens/path-regresses test |
| alphafold-grid-math | `research/test_independent_dependency_oracle.py` | `f9e8af11776503f92563450130843b86779df9c8` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_event_clock.py` | `ed0216edc6c23d1905974c857fde4c89d8585ca4` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_gaussian_stability.py` | `ac9561a5e5037617a59fd05912467933c5c32631` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_gradient_oracles.py` | `e474afc790c9bb80072a9d75198e89fed2f63892` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_horizon_oracle.py` | `d6913b58ea85a3a81ab75d1d24c8ba7cb4060912` | HOLD pair until Decimal expectation repaired |
| alphafold-grid-math | `research/test_independent_ledger_oracle.py` | `579c03a244e482309d62ff912d83f6cf2fdb236e` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_metamorphic_contracts.py` | `0ea43e4425661958cd79da90ad15dbe81aac62e3` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_normalization_oracle.py` | `6c9f5c9899362eae0bdc0e76ce58acc6286de1e6` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_numpy_oracles.py` | `4bcb28fb51a304ad857189a74dc700560f18bdcc` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_precision_oracle.py` | `ba02d4ab57aaa53a58f822d294e28b39d92131b2` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_provenance_oracle.py` | `7be818839bc9a1a06dae55837ffd14f50508a699` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_purge_oracle.py` | `172c4f0b682322bf1172b83e3591292f0376b0be` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_series_identity.py` | `028c29ad1d928ed556f3e9b4946e7729b367b1e5` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_snapshot_integrity.py` | `296e58788f89734638a633713c5aaa7c82cb4717` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_time_oracles.py` | `78381817017d007595f2b2c216eb1dfb2c0d5cef` | SKIP: root identical |
| alphafold-grid-math | `research/test_independent_timestamp_units.py` | `dbadc09ac5f692773a1f5cd565a70c72c59c25c8` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_independent_watermark_oracle.py` | `1f8046e5aac4d3e16ce98f39f5c343acfaa724c0` | OPTIONAL test-only reference; pair with production differential adapter |
| alphafold-grid-math | `research/test_math_contract_reference.py` | `14675ad7e163cc13631f47c77ba6e313365d95a6` | KEEP ROOT: source weakens/path-regresses test |

## Reproduction

Extract git-show blobs into disposable work/final-model-math-probes, place root and probe directory on PYTHONPATH, set OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1, then use existing financial-venv/Scripts/python.exe:

```
-m pytest -q -o addopts='' ../final-model-math-probes/tests/research --disable-warnings --maxfail=5
-m pytest -q -o addopts='' ../final-model-math-probes/research --disable-warnings --maxfail=5
```

Logs: work/final-model-math-probe.log and work/final-math-probe.log. Full source blob manifest: work/final-model-math-probes/manifest.json. An initial unredirected invocation returned no visible output and is not used as evidence; the logged bounded reruns above are the result basis. Source/root worktrees remained unchanged.
