# G0 trust and replay adversarial review

Requested source: PR #21, `f60869686a51693799b4844a1af49c9b39ba45d5`.
GitHub metadata and a fresh `refs/pull/21/head` fetch both confirmed that exact
HEAD before work on 2026-10-27. Review branch: `parallel/g0-trust-replay`.
The Draft PR targets `integration/alphafold-financial-system` so its diff is
limited to this review, tests and mandatory test selection. No production
verifier, admission implementation, native component or workflow is changed.

## Results and trust boundary

| Area | Checked behavior / limitation |
| --- | --- |
| Ed25519 | Fresh independent owner/provider software keys; both real signatures required. Invalid or missing second signatures fail closed. No fixture private keys committed. |
| Domain separation | Signer uses literal `STRATTESTER_G0_TARGET_BINDING_V1` followed by one NUL, independently of verifier constants. Bare, missing/double-NUL and G1/other domains reject. |
| Identity | Exact policy owner/provider IDs and key scopes; shared key, duplicate scope and same-authority substitutions reject. Distinct key bytes cannot establish distinct real-world controllers. |
| Key validity | Both keys checked at issuance and verification time; inclusive endpoints tested. Revoked, not-yet-valid, expired and wrong-scope keys reject. Trust-store pin freshness remains an independent obligation. |
| External pins | Manifest, policy and trust bytes are independently pinned. Even semantic-preserving byte edits reject under unchanged pins. Recomputing all pins is deliberately treated as caller authority, never as independent trust provisioning. |
| Binding | All 15 release, VM/provider identity, namespace, snapshot, rollback, delivery, control and evidence digests checked individually, with genuine re-signing. Separate tests prove every binding is covered by the signed message, even after matching policy substitution. |
| Nonce | Malformed or unsigned changed nonce rejects. A validly re-signed arbitrary nonce and repeated verification remain BLOCKED; there is no external challenge comparison or durable consume operation. |
| Rollback | Old snapshot/rollback pairs or old unrevoked trust bytes reject under current external pins. Restoring old pins together with old receipt/policy/trust and caller time can verify old assertions; this does not and must never admit G0/G1. |
| Fail closed | Malformed repinned JSON, missing input, unavailable verifier and invalid signatures yield BLOCKED/exit 2 through CLI. Successful signature checks also yield BLOCKED/exit 2 and preserve all denial fields. |

The receipt verifier reads three bounded, pinned inputs. Hash-shaped identity,
rollback, capture and delivery claims are not dereferenced or physically proven.
Verification time is a caller assertion, not a trusted monotonic clock. There
is no G0 admission, antirollback state, durable replay registry or execution
bridge. No test interprets a repeated successful signature check as replay
protection. Physical G0 remains `PLAN_READY_TARGET_EVIDENCE_BLOCKED`; G1 execute
and cleanup remain `NOT_AUTHORIZED`; deployment and trading remain `NO-GO`.

## P0 / P1 / P2 disposition

| Severity | Disposition |
| --- | --- |
| P0 | No new confirmed authorization/admission bypass found in this bounded software review. This is not a proof of physical safety. |
| P1 | Existing admission blockers: no durable atomic nonce history/challenge consumption, externally protected monotonic trust/policy/generation state or trusted time; no independent proof of authority, identity, snapshot/rollback or controls. A coherently rolled-back complete input set is not detectable by this stateless verifier. Keep admission disabled; implementing it requires a separate reviewed design and qualification. |
| P2 | Coverage improved: independent wire-domain oracle, all-field signed/pinned substitution cases, both-authority validity/revocation and explicit full-state rollback tests. Existing executable/library/ACL and namespace-race confinement assumptions are not qualified by these tests. No production fix claimed. |

## Reproducible validation

New file: `tests/research/test_g0_trust_replay.py` (90 tests).
Security gate: 336 -> 426 exact mandatory nodes; all seven engineering gates:
1556 -> 1646 distinct mandatory nodes. No existing node removed, threshold
lowered, test skipped or assertion relabelled as admission evidence.

Local baseline: 69 existing receipt/signature/owner tests passed. New 90 tests
passed without changing production source. Eight temporary mutations were each
detected: wrong domain, omitted provider verification, bypassed binding,
bypassed revocation, bypassed current key validity, BLOCKED upgraded to PASS,
bypassed shared-key rejection and bypassed same-authority rejection.
Source bytes were restored after each experiment. Mutation failures are expected
test-sensitivity evidence, not passing production runs.

Independent source review identified and corrected two confounded aliasing
fixtures: the shared-key case now has two genuinely valid signatures, and the
same-authority case retains valid trust scopes. Both cases explicitly verify
their signatures before asserting the authority-separation rejection. The two
additional mutation experiments demonstrate those specific guards are covered.

```text
python -m pytest tests/research/test_g0_trust_replay.py -q --basetemp=<NEW_TASK_PRIVATE_PATH> --junitxml=<OUTPUT>/adversarial.xml --json-report --json-report-file=<OUTPUT>/adversarial.json
python -m pytest -q --basetemp=<NEW_TASK_PRIVATE_PATH> --junitxml=<OUTPUT>/full.xml --json-report --json-report-file=<OUTPUT>/full.json
python scripts/financial_gate.py --gate security --sha <EXACT_HEAD> --output results/financial-ci
```

Use a new task-owned scratch path: local default pytest scratch had WinError 5,
which caused fixture setup errors before crypto ran. Explicit private scratch
resolved that environment issue; no ACL or shared scratch cleanup was attempted.
OpenSSL is mandatory, not a skipped dependency. Local Python is 3.12; OpenSSL
binary, environment and evidence file SHA256 values are recorded with the final
validation package. Full-suite and exact-HEAD hosted CI outcomes, including
failures/skips and artifact hashes, belong in the Draft PR and external evidence
index, avoiding a self-referential commit hash in this document.

Existing financial acceptance must remain BLOCKED/exit 2 for missing external
physical evidence. Green engineering jobs cannot replace it. No physical target
was selected, contacted, collected from or qualified; no G1 or trading operation
was run, and main was not merged.
