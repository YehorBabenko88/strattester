# Independent G0 qualification QA

Reviewed approved 2026-10-27 G0 v2 spec and current qualification, evidence, receipt and trust implementation. Only disposable synthetic software fixtures were used. No inventory, target selection, LS5/PC4 operations, G1, trading, database connection or external service access occurred. No production files, shared tests, CI or docs were edited. No commit was made.

## Findings

- P2: Contradictory backing volume claims accepted. `strattester/research/financial_g0_qualification.py:232` compares delivery/ACL/root hashes but omits the duplicate backing volume binding. A coherent baseline verifies, then replacing only private_evidence.backing_volume_identity_sha256 still returns contract_verified=True despite a different facts.acl_namespace_and_mounts.backing_volume_identity_sha256. The private storage identity therefore fails the approved consistency requirement. RED: test_independent_private_volume_must_match_observed_mount_volume.
- P2: OBSERVED groups accept missing auxiliary private evidence bindings. `strattester/research/financial_g0_qualification.py:236` proceeds to capture validation without requiring populated group-specific receipt hashes; `strattester/research/financial_g0_evidence.py:86` deliberately allows null for schema-only inspection. Eleven independent cases remove each auxiliary receipt/hash from an OBSERVED fact and still reach contract_verified=True, including enforcement, actual GPU evidence, executable roster, dependency metadata and ownership bindings. Keep the inspector's permissive template behavior if desired; require the receipts in qualification before claiming contract consistency. RED: test_independent_observed_private_bindings_cannot_be_null (11 cases).

No P0/P1 found. Both defects remain non-authorizing: returned G0 stays BLOCKED, G1 NOT_AUTHORIZED, trading NO-GO.

## Tests and raw evidence

Added only tests/research/test_g0_qualification_independent.py (33 cases). Reused fixture signing mechanics through runpy; independently literal attack fields and assertions. Independent helper locally aligns the initial backing volume values without modifying the shared fixture. Each test constructs its own fixture.

First required execution:
`../g0-venv/Scripts/python.exe -m pytest tests/research/test_g0_qualification_independent.py --basetemp=../pytest-evidence/independent-qa-1 -q`
Raw: ../g0-independent-qa-red.log. Result: 12 failed, 21 passed in 22.66s.

After making all independent baselines volume-consistent locally:
`../g0-venv/Scripts/python.exe -m pytest tests/research/test_g0_qualification_independent.py --basetemp=../pytest-evidence/independent-qa-2 -q`
Raw: ../g0-independent-qa-red-2.log. Result: 12 failed, 21 passed in 25.23s.

All twelve failures are genuine DID NOT RAISE ValueError assertions. No setup/import failures. The 21 passing cases cover capture strict integer/boolean/list confusion, provider/root/tree/tool bindings, authority role scope, public fixture key rejection, replay stale/namespace/cross-VM nonce reuse, public canary redaction, an explicit seven-document IO allowlist and blocked network/database/process access (signature boundary isolated only for the IO test). Positive return assertions always preserve G0 BLOCKED, G1 NOT_AUTHORIZED and trading/deployment NO-GO. Evidence directories and logs retained; no cleanup performed.

## Implementer disposition

The two independent findings were reproduced before changes and fixed by requiring
private/observed volume equality and every auxiliary collected-group digest.
The independent tests were retained unchanged. Their helper uses a coherent local
baseline; the shared fixture was also corrected to use that same volume.

Additional implementer RED cases covered malformed manifest metadata (3), replay
receipt reuse with a changed nonce (1), a private pathname escaping through a
library exception (1), absent trading NO-GO in sanitized CLI errors (1), and
boolean/integer confusion in redundant capture records (1). All have corresponding
production checks. Canonical JSON comparison preserves nested bool/int distinctions.

The first combined fix run had115passed/1failed: the new30-second positive boundary
fixture moved receipt timestamps to seconds but left its synthetic key lifetime in
nanoseconds. The key validity windows were corrected; production expiry checks
were retained. The corrected combined run passed116/116, and the subsequently
added boolean/integer regression separately passed1/1 after its observed RED.
Final combined and exact-HEAD CI evidence are recorded in the PR and delivery
inventory; these intermediate results do not certify a different commit.

The first broad local run was transitional (uncommitted implementation, before QA
fixes):12failed/1687passed/25skipped/21successful subtests. The twelve failures were
the independently reproduced defects above. This is preserved as RED evidence,
not relabeled PASS or exact-HEAD evidence. The initial default-temp setup failure
(67errors, inaccessible pytest parent) is separately preserved and not product RED.

## Remaining blockers

P0: none confirmed in this scope. P1 external prerequisites remain: no selected VM,
no physically established owner/provider/guest binding, no independently established
private storage or capture enforcement, no physical observations, no durable atomic
replay registry and no G0 admission. These are not resolved by software signatures.
P2 findings in this review are fixed; shared filesystem namespace races, verifier
library/scratch protection and physical durability remain unqualified existing
limitations. They cannot create admission through an API that always returns BLOCKED.

No actual target collection, protected LS5/PC4 operation, G1 or trading occurred.

Final combined source validation before the implementation commit:117passed,
0failed/errors/skipped/deselected in88.61s (84primary +33independent cases).
The subsequent exact-HEAD local/hosted verification is recorded separately in
the PR and sealed delivery manifest.
