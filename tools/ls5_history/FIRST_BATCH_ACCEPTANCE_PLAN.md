# F.1 independent acceptance: first-batch-only plan

NO PHYSICAL EXECUTION AUTHORIZED. No batch1, automated batches, realOOS, G1 or trading from this plan. Runtime11b6c793e6617c3de08e6ca4fa741625c54c1951/tree f3a7f9858a0ce59f425543b14e8c1d3593a1b8a9 remains installed and unchanged. Reviewed original PR69 source1bb6c99375d262564fdf439e1c88c9be8dd0176c/tree6871193180ac453ff49e08af3571952b4eaa2616; acceptance additions have a separately reported commit/package.

## Acceptance finding and publication contract
No confirmed P0/P1 collector/worker admission bypass found. Existing production collector/verifier/worker/launcher are unchanged. Standalone history_verify.py means CHECKPOINT_CONSISTENT only: it intentionally verifies before COMMITTED in the collector. It is not proof of current root tip, physical resource acceptance or execution authorization. New postrun_acceptance.py independently combines current exactCOMMITTED state/path/hash with checkpoint consistency and externally pinned controller/result/resource evidence. Treat missing root/controller evidence as BLOCKED. It does not confer realOOS/native isolation.

Actual source fixtures abruptly terminate a harmless synthetic Python child with os._exit91/92/93 after committedSQLite pages, after checkpoint publication, and before session-state COMMITTED. They bypass exception/finally handlers, preserve IN_PROGRESS, preserve already committed rows, and demonstrate no resume HTTP calls. Orphan checkpoint consistency can still verify; current-tip acceptance rejects it. Ordinary cancellation/error follows existing BLOCKED transition. No automatic recovery/reset/cleanup after crash.

## Preconditions for a separately authorized first physical batch
Hosted exact-head Linux/Windows CI must have actual successful logs/artifacts and required nodes verified first. Old runs41106550374 and41106498855 currently have no completed jobs/logs/artifacts; missing is notPASS. Owner must authorize the NEW package runner/MANIFEST/ZIP hashes and these proposed writes/budgets. No authorization implied here.

Read-only commands, using PowerShell7.6.5 on LS5 under LS-5:
```powershell
$PSVersionTable.PSVersion
[Environment]::MachineName
[Environment]::UserName
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,FreePhysicalMemory
Get-Volume -DriveLetter C | Select-Object DriveLetter,SizeRemaining
Get-Service -Name postgresql-x64-18,Tailscale | Select-Object Name,Status
Get-Process -Name postgres,tailscaled -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,StartTime
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\Users\LS-5\AppData\Local\Python\pythoncore-3.12-64\pythonw.exe'
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\Users\LS-5\AppData\Local\Python\pythoncore-3.12-64\python312.dll'
Test-Path -LiteralPath 'C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79\F1-History-11b6c79\attempt-0001'
Test-Path -LiteralPath 'C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79\F1-History-11b6c79\batch-0001'
```

Host/user/version must match. Expected Pythonw SHA d72294fb338bc2fc8896d25a7395a4db466425427e1559e77185d5135a830681; DLL9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120. Confirm pinned runtime200files and eight-package venv content via runner. Existing services/processes must be preserved; collect only names/PIDs/times privately, never command lines, environment, credentials or DSN. Require at least2GiB freeRAM and3GiB freeC space as conservative admission headroom; if not, STOP, do not terminate unrelated processes. Both attempt/batch must be absent; any prior IN_PROGRESS/BLOCKED state or existing attempt means STOP, no reset.

Check package runner/MANIFEST/ZIP against detached externally supplied hashes; check every relative manifest path, length and SHA256 before any operation. No reparse paths. Do not use earlier F/F.1 package hashes after acceptance additions. A frozen VERSION/HEAD/tree and all source blob IDs are supplied with the new package; do not replace installed runtime or venv.

## One future command, no loop
ONLY after separate exact-hash owner approval:
```powershell
& '<APPROVED_NEW_F1_PACKAGE>\RUN_BATCH_AFTER_AUTHORIZATION.ps1' -Execute -BatchIndex 1
```

One Pythonw collector. No BatchIndex2 or automatic continuation, even when batch1 isPARTIAL. New root C:\Users\LS-5\Strattester-Physical-Test\DataFirst-11b6c79\F1-History-11b6c79. Writes only new attempt-0001 logs/raw/markers/result/controller, batch-0001/history.sqlite3/checkpoint, and owned session.lock/session-state files. StageD/E/F/StageC unchanged. Keep all outputs after success/failure; cleanup is not authorized.

Public HTTPS GET api.bybit.com443 only time, instruments-info and kline. No keys/private endpoints/proxy/redirect/retry. Max20 HTTP starts including time and complete universe pagination1–4pages; connect/read3/5s; shared max2starts/any1s and conservative1.05s bound. Frozen30d window with closed-candle buffer; only currently eligible BTCUSDT/ETHUSDT/SOLUSDT. First batch normally has2–5control requests and15–18kline page slots. With full pages and three eligible symbols, earliest-missing ordering loads15000–18000 BTCUSDT1m rows first; 30day expectedBTC1m43200, so history remainsPARTIAL. Empty/short pages or ineligible symbols can produce other distributions; never infer complete data from request counts. Full universe failure ->BLOCKED.

Worker CPU15s,wall90s,RAM512MiB,stdout/stderr1MiB. Request deadline80s includes integrity. Proposed data/evidence128MiB perbatch, sampled stop127MiB; whole session2GiB includes copies (first-batch plan does not authorize that volume). Polling/retained metrics are diagnostic limits, not kernel quotas. Controller preprocessing/postprocessing time/CPU and unobserved process-family resources are not covered by a hard total bound.

## STOP and immutable post-run
STOP on anySHA/identity/coverage/provenance/pagination/eligibility error,403/429/5xx/API/TLS error, limit, unexpecteddescendant, missingfinalmetrics, nonzeroexit, cancellation or non-COMMITTED publication. No retry, next batch, cleanup, strategy, training or service intervention. Current session is blocked after crash/cancellation/error; retain evidence for independent review.

After the one attempt, stop. Owner separately pins checkpoint and controllerreceipt hashes. Existing controller performs independent PowerShell rate validation and records final retained-handle metrics. Independent QA must additionally use postrun_acceptance.py to reject orphan/stale/current-tip mismatches, invalid result/resource evidence and disk excess. Its command is for a separately approved READ-ONLY QA environment with a privately copied complete evidence root, NOT a second LS5 process launch implicitly authorized by batch1:
```text
python -B postrun_acceptance.py --root <PINNED_EVIDENCE_ROOT> --checkpoint <ROOT>/batch-0001/checkpoint.json --checkpoint-sha256 <EXTERNAL_CP_SHA> --controller <ROOT>/attempt-0001/controller.json --controller-sha256 <EXTERNAL_CONTROLLER_SHA>
```

No collector/backtest/training/API operation is performed by this oracle. Physical invocation on LS5, if desired, needs its own controlled Pythonw/read-only-verifier plan and explicit approval. A copied root establishes consistency of that captured snapshot, not live-host freshness or hostile-host rollback resistance. Record separate COMPUTATIONAL_CONSISTENCY, CURRENT_COMMITTED_TIP, RECORDED_RESOURCE_ACCEPTANCE, HISTORY_DATA_STATE (expectedPARTIAL), and CI_READINESS. No combinedphysicalPASS when CI or mandatory evidence is absent.

## Worst-case resource accounting
Every successful batch retains one FULLSQLite copy. At16batches and128MiB observed perbatch limit, stored batch/attempt ceiling is nominal2GiB plus tiny root metadata, subject to the sampled session cap. SQLite DELETE rollback journal can transiently duplicate modified predecessor pages in addition to the new copy; old copies are also retained. Budget actual S=sum(D_i+attempt_i+journal_i)+rootmetadata, not only finalD_N. Hash/verification reads ancestors and current DB repeatedly, amplifying I/O and CPU.

Using StageD1748992bytes/day only as an estimate, full30d DB ~52469760bytes. Nine full-size retained copies would be472227840bytes (~450MiB), eleven577167360bytes (~550MiB), sixteen839516160bytes (~800MiB), before raw attempt bodies, journals and logs. With8MiB accepted transport bytes/batch and1MiBstdout cap, add up to144MiB nominal16batch raw/log allowance, plus SQLite journal/transient expansion. F1 also stores the FULL repeated universe response in each accumulated SQLite, unlike the StageD history table used for this rough scaling. At saved universe size865822bytes, its extra cumulative copy component is U*N*(N+1)/2:38961990bytes for9batches,57144252for11,117751792for16. Thus the simple30xStageD estimate understates F1 metadata/copy amplification. Future universe sizes/pages can increase it further. Actual distribution/schema/page sizes may differ; these are not physical measurements or strict worst-case enforcement.

Accepted worker CPU ceilings nominal16*15=240CPU-seconds; observed wall ceilings16*90=1440seconds. These do not bound controllerC#compile/hash/I/O overhead, scheduling/poll overshoot or all descendants. TLS/read waits can exhaust wall before20requests; no promise of READY within the proposed budgets. True hard worst-case disk/total CPU/wall cannot be proved without kernel quotas/IO bounds/native process-family qualification, which remain blocked. First batch is an isolated diagnostic attempt, not G1 or deployment.

Source fixtures and source review support conditional software readiness only. F1_PHYSICAL_BATCH_1 NOT_AUTHORIZED; F1_AUTO_BATCHES NOT_AUTHORIZED; REAL_OOS NOT_AUTHORIZED; G1 NOT_AUTHORIZED; TRADING NO-GO.
