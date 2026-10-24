# Independent final readiness diff review

Reviewed 2026-10-24. Base: 67301726d250973602b964adabdb9eb8d50d0f13. Scope: uncommitted changes to financial acceptance/checkpoint/snapshot, gate manifest and tests, docs/readiness, and physical_g0_inventory.ps1. No repository edits, installations, physical database connections, application/service changes, remote node probes or G1 operations.

## Finding: P1 — failed-publication cleanup can delete an unrelated replacement

Location: strattester/research/financial_checkpoint.py:60-61 (new exception cleanup after verified_bytes).

The code checks path.lstat() against staged_identity, then separately calls path.unlink(). An actor with directory write access can replace the pathname after lstat returns and before unlink executes. The unlink then removes the unrelated replacement, contradicting the new comment that only this publication's inode is removed. This deletion path is introduced by this diff; before it, failed post-publication verification/cleanup did not exist.

Independently reproduced in a disposable work/tmp-g0-final-review-nepflqz5 fixture, using the existing venv. A bounded fault injection made verified_bytes raise ValueError, then scheduled os.replace(preexisting_known_good, target) at entry to Path.unlink after the ownership check. Observed output:

```
expected verification error: fault-injected verification failure
replacement raced into checked path: True
unrelated replacement deleted: True
```

This is a deterministic interleaving reproduction under the same shared-writable-directory threat assumed by the staged-mutation regression. It does not establish an unprivileged remote attack or production file loss. Known-good bytes used by the probe existed only in the disposable fixture.

Recommendation: avoid deleting the final pathname on verification failure without identity-safe removal under enforced directory/handle confinement. The bounded conservative fix is to fail closed and preserve the suspect final artifact for explicit identity-reviewed cleanup. Update the mutation test's deletion expectation accordingly, and add a regression that a replacement survives failed verification. Full Windows confinement can remain an explicit G1 blocker; it need not be invented in this patch.

## Checks and positive evidence

- Independently ran the physical acceptance/artifact tests, existing financial acceptance/checkpoint tests and Grid specification-reference tests: 50 passed in 10.86s. Existing venv; pytest basetemp only work/tmp-g0-final-review-tests; cache provider disabled. This passing suite does not cover the cleanup race above.
- Acceptance now compares against repository-owned gate/node requirements, rejects boolean schema versions, and cannot yield PASS from caller external claims. Every successful software aggregation remains BLOCKED, trading NO-GO, physical_g1 NOT_AUTHORIZED; self-report authenticity is explicitly unverified.
- Snapshot admission adds single-link checks and checks opened-file/path identity; bounded JSON root/depth/nonfinite handling is materially improved. These checks do not establish whole-directory confinement, which the docs accurately leave blocked.
- The Grid HMAC/reference tests are clearly labeled test-side examples with public fixture key, and the documentation expressly denies native exporter, producer authentication or real cross-DB coherence evidence.
- G0 collector source contains local metadata reads and stdout JSON only: no SQL, DB open, install, service/process control, outbound request, environment dump, command-line capture or credential retrieval. Hostname/path/process/service metadata are retained intentionally; listener interface addresses are redacted. I did not rerun the host collector.
- G0 documentation explicitly records unsigned owner approval, unknown remote nodes, absent hard resource limits, missing ACL/reparse confinement and no G1 authority. Baseline system/model/security audits identify their reviewed SHA and do not claim current end-to-end readiness.

## Disposition

No P0 found. One concrete introduced P1 requires correction before calling the software patch complete. The independent broader system/model/exporter/GPU/crash-recovery blockers should stay BLOCKED; resolving those external capabilities is not a prerequisite for an honest software-only readiness report. No approval to merge main or begin G1 is given.

## Follow-up disposition — cleanup P1 corrected

Bounded recheck on 2026-10-24 after integration fix: save_checkpoint now verifies the published bytes and propagates failure without any final-path unlink. The unregistered final artifact is preserved for operator recovery. The incorrect inode-check-then-delete cleanup and its ownership guarantee are removed. This closes the introduced P1 reported above without pretending to establish full filesystem confinement.

The new test_failed_publication_never_unlinks_a_raced_replacement schedules the same replacement at final-path unlink and fails if that deletion is reintroduced. The staging-mutation test now expects a preserved failed final and no successful returned digest. Independently reran test_physical_artifact_attacks.py, test_financial_checkpoint.py and test_financial_snapshot.py: 20 passed in 7.59s, with scratch only under work/tmp-g0-final-review-fixed and pytest cache disabled.

No remaining introduced P0/P1 identified in this bounded recheck. Routine integration follow-up communicated: add the new replacement regression to the pinned security gate manifest (it was absent and minimum remained 52 at review time). Current READINESS.md accurately distinguishes this fix within trusted-directory scope from open recovery/confinement blockers. Overall physical/system readiness remains BLOCKED and G1 NOT_AUTHORIZED. This disposition does not approve main merge or physical execution.
