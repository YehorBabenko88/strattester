# F.1 — source-only bounded history collector

Base runtime HEAD `11b6c793e6617c3de08e6ca4fa741625c54c1951`, tree `f3a7f9858a0ce59f425543b14e8c1d3593a1b8a9`. Standalone stdlib collection adapter; installed LS5 runtime/venv, StageC,StageD/E/F and production are untouched. This PR does not change synthetic-only financial acceptance.

## Invocation boundary
PHYSICAL DOWNLOAD NOT AUTHORIZED. Future exact-hash package command after separate owner approval:

```powershell
& '<APPROVED_PACKAGE>\RUN_BATCH_AFTER_AUTHORIZATION.ps1' -Execute -BatchIndex 1
```

Subsequent batch requires separate approval and two EXTERNAL pins from the preceding successful attempt, not values inferred from an untrusted checkpoint:

```powershell
& '<APPROVED_PACKAGE>\RUN_BATCH_AFTER_AUTHORIZATION.ps1' -Execute -BatchIndex 2 -PreviousCheckpointSha256 '<approved checkpoint SHA256>' -PreviousControllerSha256 '<approved controller receipt SHA256>'
```

No loop/bulk launch command is provided. Fixed dedicated root `C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79\F1-History-11b6c79`: `attempt-NNNN` logs/raw/markers/controller; `batch-NNNN` new SQLite/checkpoint; fixed session lease/state. Each new database is a verified COPY, previous batches are never written. Existing attempt/batch -> STOP. Next physical batch cannot be admitted after nonzero/resource-unverified predecessor: worker independently hashes controller/result and verifies resource status, checkpoint binding and external pins.

## Collection contracts
One worker, at most20 HTTP requests INCLUDING server time and full active linear universe pagination (max4pages) on every batch. Only public GET api.bybit.com:443 `/v5/market/time`, `/v5/market/instruments-info`, `/v5/market/kline`. No API keys/private endpoints/proxy/redirect/HTTP retry. Connect/read3/5s. Data transport rate limiter retained from the LS5-validated package: atomic single-flight monotonic admission, max2 starts in any1s, conservative1.05s completion bound, failed requests consume slots. Separate Python/PowerShell postrun rate checks. Owned-directory exclusive file lease serializes batches; restart cooldown rechecks monotonic elapsed for>=1.05s before any new HTTP request. This is not a host-wide limiter for unrelated applications.

Frozen30d closed window,5m aligned with60s buffer, fixed BTCUSDT/ETHUSDT/SOLUSDT. Each must exist in fully paginated Trading universe as eligible linear perpetual, launched before start, not delivered within window. Missing/unknown/ineligible symbol -> blocked eligibility; do not fill fabricated history. Ready instruments can complete independently; overall snapshot READY only after all six datasets complete and all three current eligibility checks pass. Store raw HTTP body bytes/hash/params/UTC first-observation in SQLite sources and exact row-to-source bindings. first_observed is capture time, not historical availability; revisions and previous availability UNKNOWN.

Each missing contiguous range capped1000 grid points, earliest missing first. SHA/row/grid/Decimal OHLCV/category/symbol/closed-window validation before perpage transaction. Duplicate/replayed timestamps or pages fail. No refresh of already verified rows; empty response leaves PARTIAL, not an implicit retry. Independent read-only oracle rederives counters, full universe eligibility, linked predecessor hashes and totals, source SHA/row binding, start/end observation order and candle-close<=observation. Dataset MISSING/PARTIAL never becomes READY. Independent command (only after owner read-only approval on physical evidence): `python -B history_verify.py --checkpoint <path> --sha256 <externally pinned SHA>`.

Nominal fresh history159kline requests (3*(44+9)), but perbatch time+universe repeats: typical9batches*2controls+159=177requests; worst4universepages+time leaves15data slots ->11batches, about214requests. Hard safety ceilings256session requests and16batches, in addition to20/batch. No budget reset on page/error. Counters independently reconstructed from captures and ancestor receipts. Do not launch another batch automatically; each physical attempt separately authorized. Invalid/failed transport/cancellation blocks session; no automatic recovery from failed attempt, reset, rewind or cleanup. Previous committed evidence remains intact for separately reviewed recovery.

## Publication/recovery
SQLite DELETE journal+synchronous FULL. Source and candle page transaction atomically committed. Close DB, hash, fsync checkpoint.partial then same-directory replace; independent verify; fsync session-state transition. Directory/power-loss durability is not claimed; missing/corrupt files/IN_PROGRESS state -> BLOCKED, never inferred PASS. Externally pin checkpoint and controller receipt to reject ordinary replay/alteration; this is not hostile-host rollback resistance or owner-signature/G1 authorization.

Cancellation via new attempt `cancel.request`; checked before/after fetch, during dataset loops, before checkpoint and state publication. On cancellation/error preserve partial DB and safe failure receipt, set session BLOCKED; no automatic retry. After worker termination/resource failure, next admission requires successful predecessor controller receipt and external hashes; partial bytes are not a usable qualified snapshot.

## Proposed batch budgets (NOT physically approved)
CPU15s,wall90s,RAM512MiB,stdout/stderr1MiB. Worker request deadline80s includes integrity work. Proposed new data/evidence cap128MiB perbatch (poll stop127MiB), session2GiB including immutable copies. Estimates derive from StageD, not physical30d measurements. STOP if any cap exceeded or final metrics unavailable. File copy/full provenance verification can cost more than15s near completion; retain STOP, do not increase automatically.

Same previously reviewed Pythonw hash `d72294fb338bc2fc8896d25a7395a4db466425427e1559e77185d5135a830681`, pinned3.12.10 runtime and eight-package roster. Existing C#/PowerShell monitor sources reused without new native isolation semantics. No native sandbox blocked stage is resumed. Sampled direct-descendant detection/retained handles/audit hooks are diagnostics, NOT kernel-complete coverage or OS isolation. Unknown descendant -> capture+STOP; no direct killing of unknown processes. Global Python, PATH/firewall/services/Grid/PostgreSQL unchanged.

## Real-data research adapter
`research_adapter_contract.py` is a contract checker ONLY, always `CONTRACT_ONLY_REAL_OOS_BLOCKED`. Exact source/checkpoint SHA, linear identity and explicit ns units, chronological train/validation/test, purge+embargo, feature/label/availableAt bounds. StageE exposed interval `[1793293800000000000,1793380200000000000)` cannot be new independent OOS. Funding,slippage,historical availability and revisions each have separate status; absent never means0. External verifier and independent authorization remain required; dictionary flags cannot qualify data. No financial_training/session/synthetic acceptance file changed, no automatic real-data route.

## Tests and provenance
Run only source fixtures: `python -B tools/ls5_history/run_source_checks.py --output <NEW_EVIDENCE_DIR>`. The committed REQUIRED_TEST_IDS.json is enforced: missing/skipped/deselected counts are explicit; skipped mandatory nodes fail. New workflow covers Linux/Windows Python3.12/3.13, Windows Parser/C#source compile and diagnostic fixtures; never executes worker main or real HTTP. One harmless Python subprocess exercises SQLite audit hook on a newly disposable fixture; no physical collector/native monitor launch. Synthetic155520-row test proves9batch/177request resume without re-download. Source-only independence review requested; real financial outcome/native isolation/GPU acceptance are outside scope.

Imported transport/rate/monitor sources come from sealed StageD/E packages; SOURCE_PROVENANCE.json records exact SHA256 and reasons. No dependency added beyond stdlib and existing pinned certifi at physical execution. Source candidates are not physical qualification. G1 NOT_AUTHORIZED; realOOS NOT_AUTHORIZED; TRADING NO-GO.
