# Per-row declared funding assessments

Additive API `assess_paper_funding_rows(packet, *, now_ms)` returns a tuple for every visible derivatives_ticker row in original order. Each result contains row_id, funding_status, evaluated_at_ms, source_request_sha256, row_sha256, fields (present values including null), field_observations (original field proof clocks/hashes), and field_states for all three funding keys. States distinguish OMITTED, EXPLICIT_UNKNOWN, PROOF_MISSING, STALE and KNOWN_SOURCE_FIELD.

Each row reuses the existing packet, payload, Math numeric, proof and use-time qualification. It never borrows the packet last-row funding_status. Overall known also requires the existing consistent producer context. Field clocks remain caller/producer declarations, not physical/PIT/source authority. The request, row hashes and original packet are unchanged; results are detached. Existing last-row-only paper_funding_at behavior is unchanged. No SQL, route, store, prefix reseal, risk or financial algorithm is introduced.

Terminan owns the policy that explicit unknown latches its gap and whether later fresh field proofs can recover; this helper reports facts without clearing consumer state.
