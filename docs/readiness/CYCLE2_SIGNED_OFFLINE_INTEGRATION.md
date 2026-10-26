# Signed offline financial integration — cycle2

Authority: owner next-cycle request; source control point f35be5fbc915b528319610105acbcc9982ba55bb. This continues the approved offline architecture. Main merge, production DB mutations, physical G1 and trading are forbidden. Exact successor source SHA and completed hosted receipts belong to the final evidence packet/PR body, not a self-referential commit hash in this file.

## Result and trust boundary

The new accepted research route is `load_attested_export` → immutable Snapshot → `run_attested_offline` → features → equations-v2 structural network → typed prediction with full provenance. Actual learning/checkpoint publication/verified reload/backtest is exercised on signed synthetic data. `register_financial_research(registry,research_only=True)` creates a REAL registry entry, disabled by default. Execution additionally requires explicit enable and `execute_financial_research(...,research_only=True)` with exact FinancialResearchContext. Generic mutable-store StrategyContext is rejected before any read; no SyncEngine or order client is reachable from this concrete route. There is no automatic registry bootstrap or production activation.

`financial_offline_bridge.run_verified_offline` is the earlier unauthenticated engineering helper, NOT the accepted signed Grid route. Producer allowlist strings and SHA alone are not producer authentication. No new route calls the old helper.

Signature verification uses a separately provisioned producer trust store pinned by an external expected SHA, fixed Ed25519 public-key encoding, key producer scope/revocation/validity, and an independently pinned existing OpenSSL executable. No artifact-selected executable, key, provider or arbitrary signature callback. RFC8032 vector2 is independent of signing fixtures; source [RFC8032§7.1](https://www.rfc-editor.org/rfc/rfc8032.html#section-7.1), [OpenSSL pkeyutl documentation](https://docs.openssl.org/3.5/man1/openssl-pkeyutl/). No new dependency/application was installed locally. NumPy is now explicitly declared for mandatory independent CI oracles.

Signed manifests bind exact schema/version, producer/build/key/export IDs, source membership/schema/snapshot IDs, coherence epoch, cutoff, completeness/history attestations, market partitions, snapshot length/hash/count, issue time and scope. Trusted policy supplies verification time independently of artifact data; key must be valid both at issue and verification. Exports older than15minutes at that policy time reject. Fixture sources cannot be upgraded to producer-attested research scope. Forecast availability must be at/after verification and before horizon end; no pre-export trade entry is permitted. Historical simulated-time OOS requires a separately explicit protocol; this route does not silently backdate actual availability to market origin.

Signature authenticates producer assertions; it cannot restore absent historical truth. Native Grid at d537d525296ef34f727996e240ae6c60102c6082 remains BLOCKED. Eight exact Git blob receipts prove source scope only. Actual DB schema state, first-availability/revision history and coherent PG/SQLite/shard epoch protocol are absent/unverified. The native guard always refuses export before physical IO; no missing facts were fabricated.

## Streaming, budgets, cancellation and recovery

`stream_offline_jobs` is lazy: default32requests, hard cap256, one checkpoint/model at a time, default512MiB work-admission budget. Each request is charged17MiB of worst-case serialized input BEFORE inference, covering snapshot8MiB/checkpoint8MiB/manifest256KiB/trust64KiB. Total default input charge512MiB; operator/model admission remains separate from hard OS RSS enforcement. Cancellation checks precede input consumption and each major verification/inference stage. Torch operations themselves are bounded and not asynchronously preempted.

Experiment preparation now admits aggregate tensors/metadata before feature allocation, uses streaming byte-identical dataset fingerprints, bounds generators/folds and checks cancellation. Training label validation follows bank admission. Numerical score overflow and malformed holdout policy fail before publishing checkpoints.

Result journal publishes a complete fsynced result inside an atomically renamed directory, creating no hardlink alias. Replay recomputes expected payload first and verifies exact bytes, not a colocated checksum. A complete interrupted stage can be promoted on restart; partial/mismatched stages are preserved and listed. Entry cap64 and result cap1MiB bound accumulation. Tests actually os._exit before/after publication and recover; identical/conflicting concurrent writers cannot replace a completed result. No automatic destructive cleanup. Trusted scratch ACL/native namespace protection and power-loss directory durability remain external requirements. Earlier checkpoint publisher abrupt-exit orphan recovery is not falsely described as completely solved by the result journal.

## Independent review and severity disposition

- P1 FIXED: incoming triangle indices differ from pinned AlphaFold `kjc,kic->ijc`; independent NumPy oracle reproduced and corrected. StructuralConfig model_equations_version=2; old/missing/version1 checkpoints reject before model allocation. No silent legacy-weight migration.
- P1 FIXED: actual Windows ancestor junction accepted by artifact/SQLite readers and checkpoint parent. Real disposable Windows junction RED→GREEN, lexical `..` rejection added before normalization. Hostile concurrent native namespace races remain BLOCKED.
- P1 FIXED: aggregate preparation/bank allocation ordering; invalid holdout could error after publication; finite Gaussian inputs could yield Inf. Independent repros and tests included.
- P1 FIXED during root review: synthetic scope relabel; key expiry checked at cutoff rather than verification; forecast availability could precede signed issue/verification. Each RED→GREEN. Fresh final reviewer independently reproduced backdating and verified rejection;64focused tests passed, no remaining P0/P1 identified under declared trusted OS/scratch assumptions.
- P1 OPEN: native Windows restricted-token/job-object/egress/handle confinement is NOT_IMPLEMENTED/NOT_RUN; prepare-only ZIP is NOT an executable sandbox. No controlled runner was installed on any live node. GRID native history/export, deployed schema, real OOS/funding/fills/liquidation/calibration, GPU and full upstream equivalence remain BLOCKED.
- P2 OPEN: source/fixture tests do not prove physical WAL/MVCC/shard recovery or all live instruments/timeframes. Actual market universe is not available; finite test matrix covers BTCUSDT/ETHUSDT/SOLUSDT/BTCUSD and linear/spot/inverse at1m/5m/1h/1d, plus same-symbol cross-market target permutation. Other positive fixed-duration integer timeframes remain contract-supported, not exhaustively production-tested; calendar durations need explicit producer schema.
- P2 OPEN: signature executable/library/scratch ACL trust must be provisioned outside artifacts; portable pathname checks do not establish atomic native confinement. No independent cryptographic CI attestation implemented; aggregator still cannot PASS or authorize G1 from self-reported artifacts.
- P3: synthetic metrics demonstrate software only. No performance/profitability claim and no unavailable math-upstream parity claim.

CYCLE2_INDEPENDENT_FINAL_REVIEW.md pins reviewed implementation hashes. After that review only tests were strengthened: two concurrent writers and signed multi-market/permutation/real-training E2E; implementation bytes remained unchanged. These additional test outcomes are executor-verified, not misattributed to the earlier64-case independent run.

## Agent branches, review and selective integration

| Direction | Draft PR | Source final reference | Root independent check before import |
|---|---|---|---|
|GPT1 structural|26|5dd37a03ec710aed1b7418edf2881f9a641d0c56|pinned equations/source+NumPy diff reviewed;52scoped cases pass|
|GPT2 Grid|24|d1b1b1424d771a58d436df086bd5b7075d7561c7|8source receipts reviewed;25cases pass|
|GPT3 training|28|9f82afd1c4f048dfdaeb3eabfec90f36897735d9|allocation/publication/score diff reviewed;27cases pass|
|GPT4 mathematics|27|5a24698256058d28a36166cbd28f73a32d350904|independent Decimal/float64 tests reviewed;33cases pass|
|GPT5 security|25|d4e1132f0ab47f87bd6eaf80f728f3f4d5a4770c|actual filesystem regressions/code reviewed;20cases pass|

These overlapping counts are NOT added as unique coverage. Source NumPy collection failures were retained, then dependency declarations corrected; pending source CI never counted as success. `git cherry-pick -x` preserves every reviewed source commit; no source branch overwritten/main merge performed. PR27 duplicate NumPy dependency commit was not reimported because PR26 already supplied it.

## Readiness and physical plan

UPSTREAM_MECHANISM_READINESS: SELECTED_CPU_EQUATIONS_PASS / FULL_EQUIVALENCE_BLOCKED.
GRID_DATA_PHYSICAL_READINESS: BLOCKED.
ML_AND_STRATEGY_ENGINE_READINESS: OFFLINE_SOFTWARE_PASS / REAL_MARKET_BLOCKED.
MATHEMATICAL_SYSTEM_READINESS: INDEPENDENT_REFERENCES_PASS / MATH_UPSTREAM_UNAVAILABLE.
PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION: DENY / NOT_AUTHORIZED.
STRATTESTER_SYSTEM_READINESS: SIGNED_OFFLINE_ROUTE_IMPLEMENTED / PHYSICAL_BLOCKED.

Read WINDOWS_OFFLINE_RUNNER_PLAN.md for exact prepare-only commands and disposable G1 design: no credentials/production mounts, owner-signed exact plan, deny-all egress including child/IPv6/loopback, restricted token, native path handles, suspended-start job assignment and enforced CPU/RAM/disk/wall caps, STOP and destroy-VM cleanup. The required native launcher does not exist; missing control means do not resume/start. A signature alone cannot bypass missing controls.

Local G0 metadata is collected stdout-only with existing script; evidence identifies LS5 and protected PostgreSQL18, all existing services/processes/DBs. PC4/other node identities and owner/ACL maps unknown. Exact successor SHA, command digests, unsigned plan manifest, fresh local inventory and completed CI receipts are included in final packet. No physical G1, installation, service/production DB change, real trading or main merge occurred.

## Reproduction (existing dependencies only)

```powershell
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
../financial-venv/Scripts/python.exe -m pytest -q tests research/test_math_contract_reference.py research/test_independent_decimal_oracles.py research/test_independent_time_oracles.py --basetemp=../tmp-cycle2-repro
../financial-venv/Scripts/python.exe -m pytest -q tests/research/test_financial_signatures.py tests/research/test_financial_signed_export.py tests/research/test_financial_attested_inference.py tests/research/test_financial_research_registry.py tests/research/test_financial_offline_jobs.py --basetemp=../tmp-cycle2-repro-signed
./scripts/physical_g0_inventory.ps1
../financial-venv/Scripts/python.exe scripts/prepare_windows_offline_package.py --output ../cycle2-windows-plan.zip
```

Do not execute startup/download/sync/bootstrap/migration/pilot/service commands or the proposed physical trial. PHYSICAL_G1=NOT_AUTHORIZED; TRADING=NO-GO; PRODUCTION_DB_MUTATIONS=FORBIDDEN; MAIN_MERGE=FORBIDDEN.
