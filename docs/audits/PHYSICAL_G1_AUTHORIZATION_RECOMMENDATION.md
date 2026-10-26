# PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION — independent Windows security audit

Target PR #21 source HEAD: `4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7`, tree `5e8862ab22aa51055f96022c428b2d90f8b5abc2`.
Recommendation: **DENY / NO-GO**. This report does not grant G1 authorization.

## Observed CI
Financial-integration run 40350796074: core, math, training, integration, security, data, cpu and native component job all SUCCESS. System-acceptance-NO-GO FAILURE (intended fail-closed). Main tests 40350795804, CPU 40350796089, math 40350796217 SUCCESS. These are GitHub job conclusions, not a physical acceptance result.

Native proof artifact ID 12663194212: GitHub API SHA256 `e1b36fe9bce67baea2e7846793716f7e7f9fb0c86a613f340d323fddaaa8a396`, 19648 bytes. Other eight artifacts returned with matching source HEAD metadata. ZIP/JUnit contents and independent byte-for-byte hashes: NOT_RUN in this audit. Do not elevate API metadata to independent verification.

## P0 STOP
- Broker.cs `--launch` intentionally returns 78/BLOCKED before model creation. No full launcher; do not bypass.
- WFP component validates only owned direct TCP socket probes on IPv4/v6, not DNS/UDP/loopback/proxy/child processes or complete egress isolation.
- Restricted token removes privileges but does not establish restricting SIDs, ACL namespace or process-wide filesystem confinement.
- Signed owner plan, nonce freshness, package hash binding, independent verifier and actual disposable Windows VM qualification not proven.

## P1
- HandleComponent inherited-handle canary is not exhaustive enumeration of inherited sensitive handles; test descendants and alternate launch paths.
- LockedInput uses handle-based leaf and ancestor checks, but namespace confinement and hostile concurrent junction/reparse swaps require negative tests.
- Native component cleanup in finally uses best-effort terminate/wait; force-failure cleanup evidence needed.
- CPU/memory limits are queried at component level; test real exhaustion, timeout, output byte limits, cancellation and process-tree escape.

## P2
- Independent replay of every original ZIP/JUnit and job attempt, compare SHA256 and required node IDs to pinned manifest.
- Verify Windows ACL, services, ports, process identity and firewall with owner-approved read-only G0 on target nodes.
- Review current Codex launcher at exact new HEAD when it exists; this review covers the target candidate only.

## Physical acceptance stages
G0 read-only inventory → Sandbox readiness → Disposable VM G1 → coherent immutable Grid snapshot → real untouched OOS → Final independent acceptance. Each transition requires its own signed evidence, exact source/binary/policy hashes, time/nonce, test manifest, cleanup proof and separate owner approval. Any missing, stale, skipped, self-asserted or inconsistent evidence means STOP/BLOCKED.

## Actual tests executed by this auditor
No native component process, G0, G1, or disposable VM tests executed. Source review and hosted CI metadata inspected. New adversarial unittest source committed; execution and CI remain NOT_RUN until observed. No LS5/PC4 changes, production DB writes, live trading, or integration branch edits.
