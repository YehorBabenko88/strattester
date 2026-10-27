# Direction6: reproducible gate ZIP consistency audit

Baselinef60869686a51693799b4844a1af49c9b39ba45d5/tree0f7626787ec835a9a945a8e576d19181044f23ec.
Only this lane edits new financial_ci_artifacts library,standalone audit script,
test_parallel_ci_artifacts and this document. No PR21 mutation from this branch.

Earlier package verification drivers lived outside versioned source. New bounded
read-only audit_gate_archive consumes independently pinned metadata and exact
expected SHA/run/repository/gate/required nodes. It verifies archiveSHA256/size,
exact3member roster,no extraction/traversal/duplicate/symlink/encrypted members,
compressed8MiB/member8MiB/total16MiB budgets and CRC. It reconciles normalized/raw
pytest/JUnit identities,subtest parents,collected/passed/skip/deselection accounting.
JUnit is UTF-8 only; DTD/entity declarations and NULs reject before parsing.

It is **consistency**, not authenticated execution. Candidate metadata and external
pins still require independent GitHub/workflow provenance review. No job identity
or execution/physical authority is created. Output alwaysBLOCKED/exit2, including
VERIFIED_ONLY consistency. Existing acceptance external blockers are unchanged.

```text
python scripts/audit_qualification_artifact.py --archive <ABSOLUTE_ZIP> --metadata <ABSOLUTE_API_ROW> --metadata-sha256 <EXTERNAL_PIN> --required-manifest <PINNED_SOURCE_MANIFEST> --required-manifest-sha256 <EXTERNAL_PIN> --sha <SOURCE_SHA> --gate security --run <EXPECTED_RUN_ID> --repository <EXPECTED_REPO_ID>
```

No downloads,network,VM/provider queries,DB access,artifact extraction or writes.
CLI exceptions disclose type only. No raw metadata/provider/path error text echoed.
Actual ownerVM remainsNOT_SELECTED; G1Execute/CleanupNOT_AUTHORIZED;Deployment/
TradingNO-GO. Native stage not resumed. No independent branch merged here.

CapabilityRED10failed due absent module; initialGREEN10passed. Additional adversarial
reviewRED2failed/10passed reproduced hidden raw collected mismatch and UTF-16 DTD
bypass in the new auditor. CorrectedGREEN12passed; standaloneCLI regression added.
No existing physical/acceptance bypass demonstrated. P0:none. P1:trusted execution
attestation and physical/native/source/owner prerequisites remain absent. P2:new
auditor malformed accounting/XML gaps corrected. Fresh branch CI and integrated
required-node membership are separate evidence to be recorded by Lead.

Decompression reads are explicitly bounded by declared member bytes+1 (maximum
8MiB+1), never ZipExtFile.read() without a size. A separate resource-boundary
RED1failed regression caught the unbounded read; GREEN14passed includes the CLI.
This limits allocations even when untrusted ZIP headers understate expansion.
