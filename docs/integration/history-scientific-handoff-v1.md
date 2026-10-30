# Scientific history display handoff v1 (synthetic only)

This optional adapter consumes **only** `review_packet(...)` output already checked against the independently pinned completion receipt. It emits `terminan.history.scientific-handoff.v1` with explicit event-end, first-availability and watermark clocks and a separate forecast decision/target axis. The output is not a Math v2.1 graph, not an authenticated live feed, and not an admitted historical source. No fitting, numerical recomputation, trading, training, API listener or PostgreSQL access is performed.

**Pinned scope:** Grid #251 `28d4ae46c8ddbc0238b351e8d6b2bd29c6602ef2`; Math historical #100 `3a9c542841e160f8b1924f155aaa2d1a676dfd04`; Strattester #64 `f08d0175162074819d1ef5b1c204d110fc197c91`; Math scientific #102 `1f97e56701c0fce01dc8dd05952111fa8df3f2d1`; Terminan #53 `91e3159d9ca1621b30fe0a4b23ab490cde0128e6`. These are **different** Math commits/APIs, with no assumed combined runtime.

The consumer must label this envelope SYNTHETIC / UNATTESTED and may display it only in an explicitly opt-in read-only surface. The current Terminan #53 is **not modified** and does not consume this envelope. A subsequent separate Terminan Draft PR must validate and present the envelope without converting `event_end_ms` to `availableAt`, without substituting historical close prices as trusted scientific source values, and without local scientific arithmetic. Negative tests must cover tampered review fingerprint, clock inversions, nonfinite values, changed units and forbidden authority flags. No auto-upgrade from SHA256 checks to source authentication.

Local targeted test command after pinned Math historical fixtures are provisioned:
```
python -m unittest tests.research.test_history_scientific_handoff
```
This Draft does not claim the test executed until a real runner reports results. No G1, merge, deployment, live orders, or production DB modifications.
