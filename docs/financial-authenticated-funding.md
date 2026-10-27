# Explicit signed funding intake

This consumer verifies immutable, independently pinned Ed25519 bytes using the
existing operator-pinned OpenSSL verifier and independently pinned producer trust
store. It is an explicit research command, never ordinary CLI activation or an
automatic funding source for a signed session. No real producer or history is
provided by this implementation. `G1=NOT_AUTHORIZED`; `TRADING=NO-GO`.

```
python -m strattester.research_cli verify-funding \
  --funding <signed-funding.json> --funding-sha256 <external-sha256> \
  --policy <funding-policy.json> --policy-sha256 <external-sha256> \
  --trust-store <producer-trust.json> --trust-store-sha256 <external-sha256> \
  --openssl-exe <absolute-pinned-openssl> --openssl-sha256 <external-sha256> \
  --scratch-root <operator-controlled-scratch>
```

Success is **SIGNATURE_VERIFIED_ONLY**, not coherent historical funding admission
or financial evaluation. Output preserves source/build/schema/snapshot/epoch,
artifact, raw and canonical policy, trust and verifier digests. No listed source
or process is modified. The only subprocess is the existing bounded signature
verifier; its scratch writes remain task owned. Its deployment dependencies and
measurement-to-launch race remain unqualified existing boundaries.

The externally pinned policy is a version1 exact object containing all fields of
`FundingPolicy`: producer_id, producer_build_sha, source_id,
source_schema_sha256, snapshot_id, coherence_epoch_id, instrument,
timeframe_ns, start_ns, end_ns, knowledge_cutoff_ns, verification_ns and scope.
Instrument is the exact exchange/market_type/symbol object. Its components are
bounded and cannot contain `/`, because ledger identity is their slash-separated
tuple. Timeframe and all times are strict integer ns. Policy is limited to16KiB;
the signed funding file is limited to1MiB and10000 event rows. Caller must obtain
the policy's bytes/digest, clock and expected cut from independent trusted sources.

The signed manifest has the exact fields declared by `_ENVELOPE`, a schema digest
derived from the explicit field/unit contract, and a domain-separated Ed25519
signature over canonical unsigned JSON. Every event carries a bounded event_id,
settlement_ns, available_ns, exact decimal-string rate and rate_unit=`bps`.
Source identity/coverage and partition must match the external policy exactly.
Float/bool integer aliases, duplicate JSON keys, duplicate settlements/events,
unknown schema fields, future availability, stale/expired/revoked keys, bad
signature and cancellation fail closed. Verification occurs against key validity
both at issue and trusted verification time. Known public fixture keys cannot
authenticate `PRODUCER_ATTESTED_RESEARCH` even under renamed producer/key IDs.

Signed complete/first_availability_retained/revision_history_retained assertions
must be true, but they are not independent evidence that Grid retained those
facts. `historical_truth=NOT_ESTABLISHED_BY_SIGNATURE` remains explicit even for
an admitted producer key. Trust roles, issuance, revocation and target clock must
be independently provisioned. No root or key is accepted from the funding file.
Coherence with price sources remains externally unproven, not inferred from a
matching epoch string. Real funding/OOS remains BLOCKED until producer facts,
all settlements, historical revisions and coherent price/funding cuts qualify.

The typed result exposes an immutable FundingWindow usable in the existing
software ledger for independently reviewed experiments. Rate arithmetic preserves
Decimal bps; fixed unit entry notional, `(entry,exit]` settlement, no mark-price
revaluation, and legacy float price/cost/reporting limitations remain unchanged.
The existing ledger intentionally continues reporting
`RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED`; this capability does not
silently relabel caller-supplied windows or turn a signed assertion into real OOS.

## Source review and selective adaptation

PR35 branch `parallel/alphafold-training-backtest-audit-4f3a4bb`, source HEAD
`371f963b6897b320787ad00f7db10ba31bc216e2`, was reviewed. Its standalone HMAC
helper captures the useful requirement for an independently trusted key, producer
and epoch, but uses float rates, unbounded iterable materialization, and no full
partition/schema/coverage policy. Neither that implementation nor its tests were
imported. This is a new consumer using existing integration contracts, not an
upgrade to or test failure in the source branch. Source defects must not be
attributed to PR21. Source blobs are pinned in the adjacent provenance JSON.

Initial capability RED:25 absent-module tests. CLI/policy/package RED:5 failed,
26 passed. These show missing capability, not a confirmed vulnerability in the
baseline. Tests use genuine signatures under a publicly distributed RFC8032 key,
synthetic events and inert task-owned files; no native or physical run occurs.

## Revision audit boundary

Version 1 has no revision-selection or cancellation semantics. A signed unknown
`revision`, `replaces_event_id`, or `cancelled` field is rejected at both envelope
and event level. Conflicting event IDs or settlements are rejected in either row
order; the consumer never silently chooses the first or latest row. A newly
signed replacement file requires its own independently supplied artifact pin.
These checks establish consumer behavior for public synthetic fixtures only.
They do not establish first availability, retained producer revisions, complete
settlement coverage, or coherent historical truth. Historical qualification and
runtime funding admission remain separately BLOCKED / NOT_ENABLED.
