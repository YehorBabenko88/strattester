# Research funding event contract

`evaluate_ledger(..., funding_windows=(FundingWindow(...),))` is an explicit
software-only extension to the existing independent roundtrip ledger. Existing
calls and the nonnegative flat `funding_bps` assumption retain their behavior and
report shape. Combining nonzero flat funding with events is rejected.

Each window asserts complete event coverage for one exact opaque instrument key
over `[start_ns,end_ns]`, including an explicit empty tuple when no events are
asserted. All trade horizons must lie within their window. There must be exactly
one window for every ledger instrument and no unused windows. Callers must use
unambiguous venue/market/symbol keys; no symbol alias or market inference occurs.

All times are integer nanoseconds. Entry is settlement-exclusive; exit is
settlement-inclusive: only `trade.start_ns < settlement_ns <= trade.end_ns`
contributes. This convention gives a boundary settlement to the exiting trade,
never to the trade entering at that same instant. There is no exposure in gaps.
The contract assumes the full unit position is held throughout each horizon.

Rates are bounded decimal strings with explicit unit `bps`. Positive rates mean
longs pay shorts; negative rates reverse the transfer. Cash return adjustment is
`-position * sum(rate_bps / 10000)` on fixed entry notional. Flat positions pay
zero. Rates are bounded to absolute 10000 bps as a research input limit, not an
exchange claim. Windows are bounded to 256 and events to 10000 in total;
identity strings and decimal inputs have length limits. Decimal scale (the stored
base-ten exponent) must be in `[-64,64]`, including zero. Funding rates are
summed and divided by 10000 exactly in an isolated 80-digit Decimal context;
only the final funding cash adjustment is converted to the legacy float return.
The legacy price-return and transaction-cost ledger remains float arithmetic.
This prevents binary conversion of each rate from erasing cancellation residuals
and bounds extreme exponent inputs before arithmetic. Duplicate event IDs or
settlement timestamps within an instrument are rejected. Settlements must lie
within coverage, availability must be at or after settlement, and both coverage
end and availability must be at or before the retrospective `as_of_ns` cutoff.
This cutoff is evaluation knowledge, not an assertion that future settlements
were available to a predictor at entry.

`source_sha256` has digest syntax validation only. Neither it, event IDs, nor
caller-asserted coverage authenticates a producer or proves completeness. Reports
therefore carry `RESEARCH_CONTRACT_ONLY_NOT_PRODUCER_AUTHENTICATED`. This code
does not model mark-price notional changes, leverage, compounding, liquidation,
or exchange rounding. Tests use synthetic examples with independent Decimal cash
arithmetic; they establish implementation behavior, never financial performance.

The signed export schema and signed walkforward session are unchanged. They have
no authenticated funding-event producer input, so their existing
`NO_SIGNED_FUNDING_EVENTS` / `BLOCKED_NO_EVENT_DATA` statuses remain. No actual
funding history was obtained or invented by this change.
