# Real OOS protocol — NOT EXECUTED / BLOCKED

This protocol extends the existing financial integration design. Synthetic CPU
tests establish software behavior only. Public RFC8032 signatures prove fixture
byte verification, never producer identity or historical market performance.
G1 is NOT_AUTHORIZED and trading is NO-GO throughout this protocol.

## Admission before a real experiment

An independent data owner must supply immutable price, funding and outcome
exports, externally pinned trust/policies, producer builds and schemas, complete
partition identities (exchange, market type, symbol, timeframe), historical first
availability, revisions and watermarks. Require producer-issued cross-store
coherence evidence and independent retained-history/completeness validation.
Matching epoch strings and signed boolean assertions are insufficient. Never
reconstruct missing availability from current rows or turn fixture keys into
producer keys. Missing facts mean BLOCKED, with no evaluation.

Pin code HEAD/tree, runtime/dependency versions, every input's SHA256 and size,
signature verifier, trust store, policies, label-generation build and exact
information cut. Funding policies cover every scored market/timeframe including
flat positions and intervals with no settlements. Revision-selection/cancellation
history is not supported by funding schema v1: reject unknown revision fields;
qualify a new explicit contract before using revised historical funding.

The current signed walk-forward command deliberately accepts SYNTHETIC only.
Do not change its scope flag to run this protocol. A separately reviewed real
data/label admission path and one-use OOS registry are prerequisites; both remain
BLOCKED. No real-data run is authorized by this document.

## Preregister and seal

Before inspecting test outcomes, record and externally timestamp a manifest of
universe selection/delistings, venue/market/timeframe identities, UTC integer-ns
boundaries, horizons, label derivation, embargo, feature recipe, model equations,
seeds, optimizer steps, batching, resources and cost assumptions. Declare whether
all training samples must be visited: a bounded step count is not a full epoch.
Record warm-up/gap/revision rules and survivorship/missing-data exclusions.

Choose temporal train/validation/test intervals against market availability,
not convenient fixture counts. Purge any train/validation label with end+embargo
past its partition boundary. Independently enumerate interval overlaps. Remove
held-out instruments from both training and validation selection targets AND
their context tracks. Fit all
learned transforms, baseline parameters and label-shuffle controls on train only.
Use validation alone for hyperparameters, thresholds and Gaussian scale MLE.
Freeze these before requesting any test prediction/outcome scoring.

Each fold starts a fresh seeded model. Default forbids reuse of earlier OOS in
later train/validation. Explicit expanding retraining is separately registered
as SEQUENTIAL_RETRAINING and cannot be described as independent holdout. Test
windows do not overlap. Record all tried configurations/failed attempts; an
inspected test cannot be reused as untouched OOS after modifying the experiment.

## Score and challenge

Record raw and validation-calibrated NLL, MAE, coverage, sample counts and
per-market/timeframe/holdout diagnostics. Compare zero, train mean, persistence
and ridge under the same split and ledger. Include seeded random signal, shuffled
training labels and strictly earlier same-series feature controls; document
limitations (these are baseline controls, not a neural shuffled-label fit).
Publish all controls, including outcomes that contradict the preferred model.

Replay immutable checkpoints in a fresh process with independently supplied
hash/train/seed/config pins. Perturb only future/test labels and verify training
weights, calibration and selected thresholds are unchanged. Perturb held-out
training context and verify weights are unchanged. Run independent split and
cashflow oracles rather than deriving expected values with the scored function.

Ledger rows report exact identity/time, position, unit entry notional, simple
gross return, entry+exit turnover, fees, slippage, signed funding and net return.
Funding settlement interval is (entry,exit]; positive bps longs pay/shorts receive.
Funding availability at evaluation cutoff must be proven; settled funding is for
post-hoc scoring, never a future feature. Report funding-excluded and adjusted
ledgers separately. Current accounting assumes disjoint independent round trips
per series, liquidation each horizon and fixed entry notional. It does not model
fills, mark-price revaluation, leverage, liquidation, capacity or a pooled
multi-timeframe portfolio. Overlapping timeframe sleeves are not additive wealth.

Vary fees, slippage and funding assumptions; report exploratory block-bootstrap
intervals with dependence-aware calendar blocks. Current sample-order bootstrap
in software is exploratory and cannot establish portfolio significance. Require
multiple-testing/selection disclosure and independent statistical review before
any real performance conclusion. No acceptance threshold is invented here.

## Checkpoint/recovery and evidence

Version 1 checkpoints contain model tensors/config, training dataset hash and
seed; they omit optimizer moments/cursor. Recovery means deterministic restart
from pinned inputs into a fresh run, not exact optimizer continuation. Completed
fold sets are staged before exclusive publication. An exception during fitting
publishes no final fold checkpoint. OS failure during the publication loop may
leave unregistered final paths; kill/power-loss can leave staging orphans. Never
discover/adopt them based on adjacent digests, overwrite accepted paths or
silently mark an incomplete run complete. Inspect a known checkpoint using
`inspect_checkpoint_recovery` with external checkpoint/train/seed pins. Preserve
ambiguous files for independent review and restart in a new output directory.
Physical crash durability, directory fsync guarantees and hostile namespace
races remain unqualified; no full durable-resume claim is made.

Seal raw forecasts, labels, rows, calibration, baseline/control scorecards,
fold memberships/configuration, checkpoint provenance, input/output SHA256,
runtime and exact HEAD in an immutable evidence package. Retain failed runs and
all raw pytest/JUnit/CI logs. Verify artifact API head_sha, download ZIP hash and
per-file digests independently. SHA256 provides integrity, not trust or truth.
Require independent ML/data/accounting review; no synthetic result may satisfy
real OOS or funding-history gates. GPU/full upstream parity remain separate
BLOCKED requirements. G1/deployment/trading require separate authorization.
