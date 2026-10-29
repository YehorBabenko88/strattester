# Strattester -> central Math compute boundary (draft)

Status: CONTRACT PROPOSAL, not a live integration.

The central Math engine executes pure bounded numerical transforms and multi-domain scientific graph operations. Strattester stays experiment/strategy lifecycle owner: dataset admission, replay, training scheduling, costs/slippage/funding, OOS evaluation, audit artifacts. Grid stays immutable exchange ingestion and PostgreSQL owner. Terminan stays a presentation-only client.

## Protocol

1. Strattester pins and verifies Grid provenance **before** requesting Math: immutable dataset/revision/epoch, complete closed candles, explicit event/availability/watermark timestamps and units. Reject partial/stale/gap and untrusted identity.
2. For every experiment create immutable `run_id`, code/model revisions, snapshot digest, splitting cutoffs, seed, resource caps, trained artifacts and context. Mathematical feature DAG belongs to Math.
3. Math replies `RESEARCH_ONLY`, never `AUTHORIZED`. Its v1 offline endpoint currently accepts untrusted inline closes, so it must not be used as a verified Grid adapter or backtest approval. Adopt later pinned-snapshot endpoint when ready.
4. Strattester applies historical replay/simulation with realistic fees, slippage and funding, no forward leakage, and independently validates Math output; may generate training examples only after gate-approved provenance and label chronology.
5. Terminan presents both mathematical results and Strattester receipts, clearly separating synthetic examples from real historical data.

## Migration controls

Find duplicated implementations by dependency graph and tests, not filename alone; prioritize nonoperational research functions. Maintain old runner in reference-only parity mode until numerical and temporal equivalence established. Production Grid risk guards, execution safety checks and source integrity validations cannot simply be removed.

## Expected tests

Missing or conflicting timestamps; future feature dependency; reordered replay; source revision drift; wrong price/volume units; duplicate time bars; invalid curve values; missing fees/funding; parameter fitting on OOS labels; malformed result; mismatched math version; auth/provenance spoof; nonfinite math; broker order capability unexpectedly present.

No DSN, credentials, native execution or production changes authorized by this document.
