# Cycle 2 independent final trust/security review

Review scope: all changed implementation source against approved baseline f35be5fbc915b528319610105acbcc9982ba55bb, plus new untracked signature/export/inference/job/registry modules. Inspected relevant existing contract, pipeline, checkpoint, strategy registry/executor, new tests, native readiness assertions, and prepare-only Windows runner documentation. No implementation edits, installation, native confinement trial, production access, or service changes were performed by this reviewer.

## Finding and disposition

**P1 — prediction availability could precede export issuance and verification. FIXED and independently verified.**

At `strattester/research/financial_attested_inference.py:45`, the original check only required `knowledge_cutoff_ns <= available_ns < knowledge_cutoff_ns + horizon_ns`. A valid signed export issued 60 seconds after the cutoff and verified 70 seconds after cutoff was accepted with a prediction marked available 1 nanosecond after cutoff. This allowed consumers to backdate a trade before the authenticated input existed.

Independent original probe: `work/security-final-review/probe_backdated.py`. It used the actual OpenSSL signer/verifier and real checkpoint/inference path, with this output:

```json
{"available_ns":360000000001,"issued_at_ns":420000000000,"verification_ns":430000000000,"accepted_pre_issuance":true,"accepted_pre_verification":true}
```

The root implementer changed the lower bound to the independently supplied `policy.verification_ns`, which is already validated to follow signed issuance, and corrected fixture availability. Independent fixed probe `work/security-final-review/probe_backdated_fixed.py` confirms the earlier availability raises ValueError and exact verification-time availability remains accepted:

```json
{"backdated_rejected":true,"reason":"forecast must be available inside its future horizon"}
{"available_ns":430000000000,"issued_at_ns":420000000000,"verification_ns":430000000000,"boundary_accepted":true}
```

**Open P0/P1 findings: none identified within this review's declared trust boundary.** This is a scoped code review conclusion, not a proof of security or native isolation.

## Independent verification

Final focused suite: **64 passed in 9.53 seconds, zero skips**, on the settled working-tree source. JUnit evidence: `work/security-final-review/final-focused.xml`.

Modules tested: `test_financial_signatures`, `test_financial_signed_export`, `test_financial_attested_inference`, `test_financial_offline_jobs`, `test_financial_research_registry`, and `test_financial_filesystem_security`.

The earlier `work/security-final-review/focused.xml` is retained as transitional evidence: 17 failed and 47 passed when the root's source fix landed while the old fixture was loaded. Those failures all reported the corrected availability guard rejecting the old fixture. It is not the final test result.

The reviewed implementation uses an externally hash-pinned trust store, exact producer/key membership and issued/verification validity, canonical domain-separated Ed25519 messages, exact signed source/partition/schema/epoch/cutoff/scope checks, and byte-hash-bound snapshot/checkpoint reads. Generic mutable-store strategy execution cannot construct the required exact offline context. The explicit registry entry defaults disabled, requires explicit enabling, and produces no trades. Job iteration is lazy, request/input counts are bounded, cancellation is checked at stage boundaries, publication replay recomputes expected bytes, and abandoned partial stages are preserved. No additional P0/P1 defect was identified in those paths.

## Boundaries that remain external or blocked

- OpenSSL executable/libraries, namespace and scratch ACLs must be protected by a trusted OS/operator. Hash checking does not establish native handle confinement or eliminate hostile namespace races.
- Windows token/job/egress/handle confinement and physical G1 were not exercised and remain NOT_AUTHORIZED/NOT_RUN. Portable reparse rejection tests do not satisfy those controls.
- Directory publication/restart probes establish bounded software recovery, not power-loss durability.
- Signed producer assertions do not reconstruct missing Grid historical truth. Native Grid export remains BLOCKED. GPU equivalence and real OOS/trading claims remain outside this review and blocked.
- Resource calculations are software admission checks, not hard RSS/CPU enforcement. Cancellation occurs at bounded Python stages, not inside every native operator.

## Exact reviewed source receipts

HEAD: `262a1b2a6dabe722e581fe93e2a17c28b3b00ae9`, with the untracked and modified working-tree files listed below. These hashes, rather than HEAD alone, identify the reviewed content. Machine-readable receipts: `work/security-final-review/source-sha256.json`.

| File | SHA256 |
|---|---|
| `pyproject.toml` | `b0b7eea214b261bce7d1a90860af56245f6d9648171963ee1883a9231538e8cc` |
| `scripts/prepare_windows_offline_package.py` | `a7a191ecc854e49b30d46866f2bf1fbae48079918b60604b401c90a5f68c6bf4` |
| `strattester/research/alphafold_triangle.py` | `aa63f1852c2f6b0892a96a710639e68e2c33db6bcd64c750c4fe6efe8c816045` |
| `strattester/research/financial_attested_inference.py` | `f66fb610bd2c9ed7643edbc442547699c91b57da203b7e0e7faf4a3ec489580d` |
| `strattester/research/financial_checkpoint.py` | `71dfbd48c40a30a01a494b1ad13015d35695d5bd3d3f7f4659a4f64bf5bc0ebb` |
| `strattester/research/financial_evaluation.py` | `8a96de246b092539cdf15addec260e22cdf74a7ebbfe4ef86fb6f4a27b38f890` |
| `strattester/research/financial_experiment.py` | `4aa46cd96c85bd42008c792c0d5a2330e7788a1bc01c4fe450384b13c6c0f4d6` |
| `strattester/research/financial_offline_jobs.py` | `f57a0911b047893f5f80af821e71cfff1c7a7c99ba59f89b365528a89cacd844` |
| `strattester/research/financial_signatures.py` | `3386870f9df11ed112abd2fd24c1191b2ec51a02d1d5e076129690e7ea17bbeb` |
| `strattester/research/financial_signed_export.py` | `0283644d4bee22e8cdc6a39f45b8c726051d1a1003c61ceb5d68cc0a26d78829` |
| `strattester/research/financial_snapshot.py` | `34aae8ddbeb878d4c27284df66e51437de081d6209ef910e8b061db88f0f7edf` |
| `strattester/research/financial_structural_model.py` | `6b471c977f21dd4604690a812f070680af4a44e83807fb23d3ff727a9999c1d7` |
| `strattester/research/financial_training.py` | `03d871e01ce78d8dff0a06e87851c3c41267eed0ede908916e0e8f0218263f85` |
| `strattester/research/grid_producer_readiness.py` | `936791d17463507a5b95db0cca0bbb304e301db669ddd52a35513dddfa75bff0` |
| `strattester/strategies/builtin/financial_structural.py` | `f4189f17f6b87da5699615885a498706d2d37299725e923143f791720eba695a` |
| `tests/research/signed_export_fixture.py` | `89323ae7eb1874e1f779881aaff702f017006f83f94509c9b6b4f52806e55947` |
| `tests/research/test_alphafold_triangle_reference.py` | `411cbe52e9e7ce8f345933ac2ec47d8c4223dec968e46903557db000df32b86e` |
| `tests/research/test_financial_attested_inference.py` | `4f19171d19a7266c69f6ec556cd84aa156773d6875961efba5cfbaa9b79332c9` |
| `tests/research/test_financial_evaluation.py` | `c0dc60410019c1c4aeef5ea34ff713aaeb0fe80c8249936c66d50e35167e8683` |
| `tests/research/test_financial_experiment.py` | `355bdd2690765785d6b653d9495a64a636fe6e86de74ab59bf0242a7b6aaa7e5` |
| `tests/research/test_financial_filesystem_security.py` | `f2446f336aa741f02628a3ec821dc4d95d2b009fa187d69db798253351fb782f` |
| `tests/research/test_financial_mathematical_verification.py` | `6741792e32d5fc095c023281e77b22923e033796ec25e3770108bff05be6cb4d` |
| `tests/research/test_financial_offline_jobs.py` | `a1273abe650aacbb722cec24502b5ccec10f74c69ea2e273c37bd8f5382eb574` |
| `tests/research/test_financial_research_registry.py` | `117fad611de10cfd2e97c8f4165f167337410f04af15bc851d7b2e6d0b48300c` |
| `tests/research/test_financial_signatures.py` | `fd0abe14d2808368625e8063016f251b66faf26ff3011e3f8e9445d092433ab8` |
| `tests/research/test_financial_signed_export.py` | `5186c10c3beba3885fe7628ac5a3b9037d0a7521084cb83eb9245eb0b15f3ed6` |
| `tests/research/test_financial_training.py` | `6c32f497ccb14979879cae98de5d26fed0d1227a9b7f8a6b3fb232b745a268cb` |
| `tests/research/test_grid_producer_readiness.py` | `4e50b40a3cc59c5b065c97f08073c12e36695dd94a439740d4e200b37226273e` |
| `tests/research/test_structural_upstream_differential.py` | `fb52ec6347efcfa11bb9bc2114fa933a7eee29053f5e7de0e4820b906c8e80f2` |
