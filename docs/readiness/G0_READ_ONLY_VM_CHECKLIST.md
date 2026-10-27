# G0 v2 read-only review checklist

This is a non-executable checklist for an owner-selected disposable Windows VM.
No VM has been selected in the checked-in selection record. All target facts
remain NOT_COLLECTED. This document grants no collection permission and includes
no command runner. The blocked qualification implementation is outside scope.

## Before any owner-authorized collection

- [ ] Owner supplies the disposable VM identity and independent provider/owner
      records through the agreed private channel; no inferred identity.
- [ ] Reviewer confirms the target is neither LS5 nor PC4, nor a production
      host, database, service or shared workload.
- [ ] Owner identifies approved read-only sources and evidence destinations.
      Missing paths/ownership/receipts remain unresolved; do not probe to fill them.
- [ ] Reviewer pins the exact source/tree and admitted artifact hashes, contract
      versions and approved PowerShell versions using existing owner records.
- [ ] Owner confirms the separate observation work order and private evidence
      handling arrangements. No permission is inferred from this checklist,
      schema validation, public hashes, a self-report or hosted CI.
- [ ] If pre-existing capture protections or required evidence are missing,
      record that limitation and stop. Do not implement or change privileges,
      process controls, network policies, protected launch or host configuration.

## Review existing or separately authorized evidence

- [ ] Check JSON shape using collector schema1 / observation contract2 and
      evidence manifest version1; reject unknown versions and missing fields.
- [ ] Record each source state independently from required-field/empty policy.
      Null is unknown, not zero rows. Provider errors remain UNAVAILABLE.
- [ ] Record all ten groups from the final-report template, including required
      independent receipt slots. Collector rows cannot automatically complete
      Python/Torch, ownership, resource enforcement or GPU execution groups.
- [ ] Treat zero TCP/UDP endpoints as EMPTY only after successful collection;
      this proves no network isolation. Never infer DB ownership from port/PID/name.
- [ ] Keep command lines, credentials, raw errors, identities and private paths
      out of public reports. Retain only reviewed status and evidence hashes.
- [ ] Separate mocked PS5.1/7 compatibility results from real provider behavior.
      No local test run establishes a target's permissions or physical facts.
- [ ] Retain NOT_COLLECTED for every unobserved group; retain BLOCKED readiness.

## Stop and report

Stop on unknown identity/ownership, absent required facts, malformed JSON,
partial output, unexpected side effects or missing approval. Preserve evidence
under the existing owner's procedures; no automated cleanup, retry under higher
privilege, alternate provider, remote probe or fallback is specified here.

No DB connection, migration, checkpoint, service operation, network-policy
change, elevation, protected launch, G1, deployment or trading belongs to this
work. No operation on physical LS5/PC4 is permitted.

Use [the final-report template](G0_FINAL_REPORT.template.md) and
[observation contract](G0_OBSERVATION_CONTRACT_V2.md). The existing
[target protocol](TARGET_G0_EVIDENCE_PROTOCOL.md) describes external prerequisites;
it does not authorize this work to execute or implement them.
