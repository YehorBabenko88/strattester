# Independent target-specific G0 preparation

Baseline18581155af8d84a1c6672da99ede1488e3bed307/tree95de1c8b68637e6c7e335ae957a7af9d56228206.
Owner explicitly states VM=NOT_SELECTED; provider/UUID/owner=NOT_COLLECTED;
sandbox/evidence paths=NOT_AUTHORIZED; private delivery=NOT_DEFINED;
snapshot/rollback=NOT_VERIFIED; G0 qualification=BLOCKED; G1 Execute/Cleanup=
NOT_AUTHORIZED; Deployment=NO-GO. No fact,
authority, key, SID, ACL, path or target hardware value has been invented.

## Provisioning handoff

The read-only commands remain [G0-01 through G0-05](TARGET_G0_COMMAND_MANIFEST.template.json).
Use them with the [observation v2 contract](G0_OBSERVATION_CONTRACT_V2.md),
[ten-group evidence manifest](TARGET_G0_EVIDENCE_MANIFEST.template.json),
[private capture protocol](TARGET_G0_EVIDENCE_PROTOCOL.md) and these new review files:

1. [Trust policy](TARGET_G0_TRUST_POLICY.template.json): owner, provider and reviewer
   authority must be provisioned outside the candidate package and guest. Candidate
   digests and self-signed guest statements cannot create this authority. Verify
   exact algorithm/domain/canonical bytes, external key/policy pins, revocation,
   validity, challenge freshness and independently administered replay history.
2. [Independent identity receipt](TARGET_G0_IDENTITY_RECEIPT.template.json): bind
   provider immutable VM identity and generation to the guest observation and exact
   release/command/tool/scope hashes. A copied guest UUID or hostname does not prove
   provider identity. Private raw identity evidence stays with designated owners.
3. [Private capture plan](TARGET_G0_PRIVATE_CAPTURE_PLAN.template.json): independently
   review capture tool bytes and actual timeout/output/quota enforcement, ancestor
   ACLs, backing volume, encryption/key custody, owner/reviewer SIDs and retention.
   Do not change ACLs, encryption, services or firewall as part of this kit.

These are non-executable design/review templates. The separate
`verify-g0-receipt` software command verifies two Ed25519 binding assertions against
externally pinned policy/trust bytes. It requires different owner/provider keys,
strict purpose/domain, all expected release/VM/scope/snapshot/rollback/delivery/
capture hashes, bounded time validity and nonempty nonce. All fields must match
the external policy. It rejects public fixture keys and substituted signatures.
It reads no referenced receipt, namespace, VM, provider, snapshot or database.
Even valid signatures return BLOCKED/exit2: historical/physical truth remains
unestablished, durable replay is NOT_IMPLEMENTED, and G0 admission is not implemented.
Caller verification time is not a trusted target clock. No authority is provisioned
by this code. Existing
inspect-g0-evidence deliberately cannot turn these files or hash-shaped receipts
into approval. G1 owner-v2 is a separate domain and must not be reused as G0
provider authority. Future automated admission requires independent review.

```text
python -m strattester.research_cli verify-g0-receipt --manifest <LOCAL_RECEIPT> --manifest-sha256 <EXTERNAL_PIN> --policy <LOCAL_POLICY> --policy-sha256 <EXTERNAL_PIN> --trust-store <LOCAL_TRUST> --trust-store-sha256 <EXTERNAL_PIN> --verification-time-ns <REVIEWED_TIME> --openssl-exe <ADMITTED_TOOL> --openssl-sha256 <EXTERNAL_PIN> --scratch-root <PRIVATE_OWNED_SCRATCH>
```

The adjacent G0 binding policy/receipt wire templates are deliberately incomplete.
Generic trust-store format is version1/keys (producer_id,key_id,32-byte public key
base64,valid_from_ns,valid_until_ns,revoked); owner/provider roles are separately
pinned by policy. Do not supply real private keys; verifier consumes public trust
only. Verifier scratch is separately admitted private software scratch, not a
G0 target sandbox. Production/native/physical operations remain unavailable.

All null pins block collection/admission. After final source commit and sealed
package, fill release/tool hashes in external unadmitted manifests, never inside
a self-hashing receipt. Owner selects the disposable VM; independent provider and
reviewer supply real identity/authority receipts; then an admitted operator reviews
exact argv, capture boundary, ownership and STOP conditions. No template is executed
and no observed value is substituted from CI or the development machine.

## State and admission rules

OBSERVED is provider observation, not authenticated truth. EMPTY is successful
zero rows subject to separately reviewed empty-allowed policy. MISSING means
required facts absent from nonempty results. UNAVAILABLE means provider failure
with partial output discarded. NOT_COLLECTED means no target observation. None
alone grants PASS. Every required fact, identity, receipt and control must be
independently verified; gaps preserve BLOCKED. Failed/partial/truncated/timed-out
captures cannot be relabelled EMPTY. Unknown process/port/DB ownership also blocks.

G0 is local read-only metadata and bounded private capture only. No DB connection,
service/process control, package installation, Torch/GPU/native worker execution,
remote provider, credential dump or protected LS5/PC4 operation. Capture limits
30seconds/8MiB and disk floor2GiB are requested controls, not software enforcement.
STOP on unresolved pins/owners/ACLs/identity, unexpected IO/network/write/process,
secret exposure or bounds failure. Preserve original failure bytes privately;
public results contain reviewed hashes/metadata. Cleanup needs exact owned-object
review and separate authority; no recursive deletion or nonce-history removal.

## Software defect and forensic boundaries

Shared bounded JSON previously rejected NaN/Infinity literals but accepted numeric
exponent overflow such as1e309 as infinity. Nine adversarial G0 cases reproduced
this; no admission bypass was shown because G0 already always blocks. The parser
now rejects nonfinite parse_float results before any consumer sees them. Finite
extremes/underflow remain parsed normally and cannot authorize G0.

Historical Ubuntu3.13 FAIL40539165917/attempt1/job122312512345 and successful retry
122316177306 remain separate. Images/Python patches/regions differed. The successful
retry is not a fix; source defect/OOM/startup root cause remain unproven. Mock-only
boundary tests and20second limit stay unchanged. Fresh CI logs must be retained
with exact runner/Python identities and any boundary phase on failure. No forced
physical timeout experiment or retry loop is introduced.

PR43 remains deferred pending independent dataset/metrics/receipt/lease binding
regressions; no source imported. Signed funding proves pinned signed assertions,
not first availability/revisions or actual settlement history. Grid retained
history/coherent epoch/producer authority and real multi-instrument/timeframe OOS
prerequisites remain external facts; synthetic fixtures do not establish them.

Ten physical groups remain NOT_COLLECTED: host;OS/PS;Python;Torch/dependencies;
CPU/RAM/disk/limits;GPU;process/services;TCP/UDP;ACL/mounts;source/DB ownership.
PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED;PHYSICAL_G1=NOT_AUTHORIZED;
TRADING=NO-GO. Native sandbox stage remains blocked and unchanged.
