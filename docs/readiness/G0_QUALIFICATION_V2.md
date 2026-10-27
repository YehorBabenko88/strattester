# G0 qualification v2: pinned software consistency review

`verify-g0-qualification` adds a connected review to the existing observation v2,
manifest inspection and independent Ed25519 owner/provider verification. Success
means `contract_verified=true`, **status BLOCKED / exit 2**. It never means target
admission, private storage security, capture enforcement or physical truth.

Original approved design: [design](../superpowers/specs/2026-10-27-g0-v2-design.md).
Refreshed implementation baseline: `593cf92b1cfbfb6a04961dd7f260349c01459cc0`.

## Inputs and trust boundary

Every path and SHA256 is supplied independently by the caller, never obtained from
candidate JSON. The seven explicit files are bounded JSON with duplicate/nonfinite
rejection, strict field sets and local regular-file checks. No referenced artifact,
raw stream, target path, VM, DB or command is opened or executed. The only executable
is the independently pinned OpenSSL verifier, using its existing bounded signature
boundary and operator-protected scratch directory. Trust roots/policy pins and
trusted verification time must come from outside the candidate package/guest.

| CLI input | Budget | Contract |
|---|---:|---|
| `--qualification` | 128 KiB | Version2 G0_QUALIFICATION_CLAIMS; schema below |
| `--evidence` | 128 KiB | Existing TARGET_SPECIFIC_G0_EVIDENCE_MANIFEST schema1, observation2 |
| `--manifest` | 64 KiB | Existing signed G0_READ_ONLY_BINDING_RECEIPT |
| `--policy` | 32 KiB | Existing external G0_BINDING_VERIFICATION_POLICY |
| `--trust-store` | 64 KiB | Existing externally provisioned producer key store |
| `--review-policy` | 32 KiB | Version2 G0_EXTERNAL_QUALIFICATION_REVIEW_POLICY |
| `--replay` | 128 KiB | Version1 G0_REPLAY_REVIEW_SNAPSHOT, at most512 entries |

Each input also requires `--<name>-sha256`. Supply `--verification-time-ns`,
`--openssl-exe`, `--openssl-sha256`, and `--scratch-root` separately. See literal
software fixture in `tests/research/test_g0_qualification_v2.py` for complete wire
examples, generated with ephemeral disposable signing keys. Fixtures are not
physical authority and private keys are never included in published evidence.

## Qualification schema

The exact top-level keys are version, purpose, evidence_kind, execution_authorized,
physical_g1, trading, release, identity, capture_constraints, private_evidence,
captures. Version is integer2, purpose G0_QUALIFICATION_CLAIMS, evidence_kind is
SYNTHETIC_SOFTWARE_ONLY or UNVERIFIED_PRIVATE_TARGET_CLAIMS. The envelope requires
execution_authorized=false, physical_g1=NOT_AUTHORIZED, trading=NO-GO.

Release uses the four existing source/tree/package/command-manifest pins. All must
match the signed receipt and evidence manifest. Identity requires owner_id,
provider_id, vm_identity_sha256, provider_identity_sha256, guest_identity_sha256,
identity_receipt_sha256, snapshot_generation_sha256, sandbox_root_sha256,
evidence_root_sha256. Signed owner/provider roles and provider/VM/generation/roots
must match; guest identity must match both expected and observed manifest identity.
Distinct externally pinned keys, issue/verification validity, revocation and public
fixture exclusions remain enforced by the existing real signature verifier.

Capture constraints require wall_seconds_per_command in1..30,
stdout_stderr_bytes_per_command_combined in1..8388608, minimum_free_disk_bytes
at least2147483648, and independent_enforcement_receipt_sha256 matching the signed
capture_controls_receipt_sha256. These are checked claims, never OS enforcement.

Private evidence requires delivery_receipt_sha256, acl_scope_receipt_sha256,
evidence_root_sha256, backing_volume_identity_sha256,
encryption_and_key_custody_receipt_sha256, retention_policy_receipt_sha256,
quota_receipt_sha256, owner_identity_sha256 and reviewer_identity_sha256. All are
non-null SHA256; reviewer and owner hashes differ. Delivery/ACL/root pins bind to
the signed receipt. No raw paths, raw streams, command text or arbitrary extra
fields are accepted in this object or capture records.

Captures bind exactly the externally required unique command roster covering all
ten observation groups. Per-command argv/tool hashes, identity receipt, private
owner receipt, fact state and redundant evidence capture roster must match. Strict
integer timestamps stay within signed receipt lifetime and trusted now, and within
the declared wall cap. Combined stdout/stderr byte accounting must be exact and
bounded. Zero-length streams require the empty-content SHA256. Failed, timed-out,
truncated or incomplete captures are rejected. EMPTY is permitted only by an
explicit external empty_allowed=true; OBSERVED requires nonempty rows and every
externally required property. No result here can upgrade null NOT_COLLECTED facts.

## External review policy and replay

The external review policy requires expected pins for qualification/evidence/
manifest/policy/trust_store/replay; challenge_nonce_sha256; replay_namespace_sha256;
replay_sequence; maximum_replay_age_ns (1..30seconds); valid_from_ns and
valid_until_ns (at most24hours); and command_requirements. Each command requirement
has command_id, observation_group, exact_argv_manifest_sha256, tool_sha256,
required_fields, empty_allowed. The policy itself is externally hash-pinned.

Replay snapshots require version, purpose, namespace_sha256, sequence,
observed_at_ns, entries. An entry has nonce_sha256, vm_identity_sha256,
receipt_sha256. Nonces are unique throughout the externally selected namespace;
a used challenge is rejected even if the candidate changes VM. Future/stale
snapshots, namespace or sequence substitutions and malformed entries reject.

A snapshot is read-only evidence, **not atomic durable replay protection**. Repeated
verification of an unused challenge can return the same BLOCKED report. No nonce
is consumed and no admission is implemented. This distinction is covered by tests.

## Evidence and readiness

Dedicated CI runs pure contracts on Linux and Windows, and existing fully mocked
PowerShell5.1/7 contracts on Windows. It records the exact checkout HEAD/tree,
node IDs, raw log, JUnit, pytest JSON and SHA256 inventory, rejecting any skip in
its selected jobs. Synthetic fixture directories/private keys are not uploaded.
Full repository CI and financial acceptance remain separate; existing external
acceptance blockers must remain visible.

All ten real VM fact groups in the existing templates remain NOT_COLLECTED/null.
Owner/provider provisioning, real target identity, snapshot/rollback, private
storage ACL/encryption, independently enforced bounds and physical observations
remain external prerequisites. PHYSICAL_G0=PLAN_READY_TARGET_EVIDENCE_BLOCKED;
G1=NOT_AUTHORIZED; deployment/trading=NO-GO. No automatic VM selection, physical
collector execution, protected LS5/PC4 operation, G1 or trading occurs.

The qualification/review-policy templates adjacent to this document deliberately
contain null target/authority/capture slots and are rejected by verification until
independent evidence exists. They are not executable instructions. Existing real
fact templates remain unchanged: all ten groups are NOT_COLLECTED/null.

Additional consistency rules require every collected group's auxiliary receipt
hash, agreement between private and observed backing volume, strict metadata
containers, and type-preserving equality of duplicate capture records. Replay
snapshots also reject an already recorded receipt hash if its nonce is changed.
Library exceptions suppress private filenames/values and chained raw errors;
CLI errors remain BLOCKED, G1 NOT_AUTHORIZED and trading NO-GO.

Independent review and regression disposition: [QA](G0_QUALIFICATION_V2_QA.md).
Financial security gate now includes all117 added qualification nodes, increasing
its mandatory roster from402 to519 without removing any prior node.
