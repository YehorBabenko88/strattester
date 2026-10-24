# Windows native research sandbox — independent QA / G1 readiness

Reviewed integration PR #21 at `67301726d250973602b964adabdb9eb8d50d0f13`.
**PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION: DENY / NO-GO.**
Current implementation is a **non-executing admission prototype**, not a native launcher. No VM or LS5/PC4 physical tests have been performed.

## Native implementation acceptance requirements
1. C++/Win32 privileged broker must create restricted primary token with explicit privilege removal, restricted SIDs and no admin-equivalent rights; verify effective child token, integrity level and groups.
2. CreateProcessAsUserW suspended, explicit PROC_THREAD_ATTRIBUTE_HANDLE_LIST with no sensitive handles, create Job Object, apply active-process=1, kill-on-close, CPU rate and process/job memory limits, assign process to Job before ResumeThread. Validate effective limits and all handles, including nested job compatibility; deny on error.
3. Wall clock watchdog and bounded output must terminate job and await process exit; no partial output may become READY. Handle forced kill, crash, concurrent launches and cleanup.
4. Trusted-root filesystem access must be mediated by Windows handles, reject reparse tags at each component, ADS, UNC/device/extended paths and post-validation substitution. Lexical prefilter is not sufficient.
5. Deny-all egress requires independently managed and attested OS policy for child identity/process tree across IPv4/IPv6/DNS/loopback. Firewall rules alone must be assessed against loopback and local services. Missing network enforcement => no resume.
6. Broker binary and policy must have trusted signatures/hashes, immutable package, independent owner authorization, no mutable user-controlled DLL/PATH/TEMP, no token or handle leakage. No fallback to normal subprocess.

## Disposable Windows VM adversarial matrix
Required tests: forbidden file open, IPv4/IPv6/DNS/loopback, child escape, junction/symlink/ADS/device, handle inheritance, CPU/RAM exhaustion, timeout/cancellation, crash/partial output, cleanup/retry, TOCTOU package substitution, authorization substitution, missing constraint. Each must record exact binary SHA, VM snapshot ID, OS build, policy hash, exit code, OS evidence, JUnit and signed receipt. None executed yet.

## Strattester integration QA
CLI/registry/SyncEngine/ResearchRunner, SQLite/PostgreSQL sharding, AlphaFold model/checkpoints, artifact loader, provenance, GitHub Actions JUnit and required node IDs must be tested separately. Hosted seven component jobs success does not override failed system acceptance.

## Staged physical decision matrix
- **G0:** owner-approved read-only evidence for OS/token/ACL/services/processes/ports/firewall and binary signatures; no state changes
- **Sandbox readiness:** native broker, OS enforcement and independent verifier tested on disposable Windows VM
- **Disposable G1:** isolated synthetic process only, no credentials, production DB or trading
- **Grid snapshot:** immutable coherent exported data, verified provenance and availability timestamps
- **Real OOS:** untouched chronological holdout, independent metrics and negative controls
- **Final acceptance:** independently validated artifacts, required node IDs, zero skips, owner authorization and explicit NO-GO-to-GO transition

Every transition requires fresh evidence from a separate authority. BLOCKED, NOT_RUN or self-attested PASS cannot authorize the next stage. No G1 on LS5/PC4.
