# G0 v2 Qualification Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task. Engineering implementation and independent QA are authorized by the user.

**Goal:** Validate connected G0 identity, external trust, bounded private capture and target manifest claims while always blocking admission.
**Architecture:** Add a pinned read-only qualification verifier composed with existing two-signature verification and observation inspection. No target runner or durable replay writer.
**Tech Stack:** Python stdlib, pytest, pinned OpenSSL Ed25519, mocked PowerShell contracts, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-10-27-g0-v2-design.md (original approved design; refreshed baseline 593cf92b1cfbfb6a04961dd7f260349c01459cc0).

## Global Constraints
No physical collection, automatic VM selection, LS5/PC4 operation, G1, trading or main merge. Real VM facts remain NOT_COLLECTED/null. G1=NOT_AUTHORIZED; TRADING=NO-GO. Synthetic fixtures never establish physical truth. Preserve evidence; no cleanup.

## Review Focus
- Cross-document owner/provider/VM/generation substitution must reject even after resigning.
- Boolean integers, timeout/truncation and combined stdout/stderr accounting must reject.
- Replay snapshots are externally pinned review evidence, never durable replay protection.
- Public outputs and exceptions must not echo private paths, identities or raw streams.
- Every explicit input is bounded/hash-pinned; no referenced path, tool or VM is opened.

### Task 1: Connected qualification contract
Files: new strattester/research/financial_g0_qualification.py; tests/research/test_g0_qualification_v2.py; runtime module roster.
Interface: verify_g0_qualification(*, qualification_path/sha256, evidence_path/sha256, manifest_path/sha256, policy_path/sha256, trust_store_path/sha256, review_policy_path/sha256, replay_path/sha256, verifier, now_ns) -> always BLOCKED report or ValueError.
- [ ] Write literal-schema synthetic fixtures and rejection tests, including signature identity, external policy, nonce/replay, capture/private evidence, observation schema and redaction boundaries.
- [ ] Run tests against baseline and retain genuine RED output.
- [ ] Implement strict bounded pinned verification with existing real Ed25519 verification; preserve all admission blockers.
- [ ] Run tests GREEN and existing G0 regression suites; record outputs.

### Task 2: CLI and CI integration
Files: strattester/research_cli.py; .github/workflows/g0-qualification.yml; docs/readiness/G0_QUALIFICATION_V2.md; qualification template.
- [ ] Add CLI tests proving blocked exit2, sanitized errors, no physical operations.
- [ ] Observe RED then implement CLI and package roster.
- [ ] Add exact-HEAD dedicated CI on Windows/Linux, retain JUnit/raw evidence and SHA256 manifest; include independent QA file.
- [ ] Run repository pytest and relevant exact-node gates; retain all failures/skips.

### Task 3: Independent QA and delivery
- [ ] Fresh reviewer independently evaluates implementation and writes adversarial tests without using production constants; retain review and RED/GREEN fixes.
- [ ] Publish design, contract, evidence inventory and limitations, commit and push named branch.
- [ ] Create Draft PR against integration/alphafold-financial-system; inspect exact-HEAD CI and record links/status.
- [ ] Deliver exact HEAD/tree/files, evidence SHA256, P0/P1/P2/readiness and principal blockers to lead Codex.
