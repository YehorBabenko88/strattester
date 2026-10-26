# Signed synthetic offline walk-forward

`prepare-walk-forward` creates twelve genuinely Ed25519-signed synthetic origins,
three instruments, two timeframes, a separate trust store, an untrained bootstrap
checkpoint, and a pinned synthetic label dataset. Its RFC8032 key is public test
material. Signatures attest snapshot bytes and declared source facts; they do not
prove real historical truth. Direct labels are caller-pinned synthetic log returns,
not producer-attested market labels. Real OOS and trading remain blocked.

From a checkout, using the qualified Python environment and independently reviewed
OpenSSL executable/hash:

```powershell
$py = '../financial-venv/Scripts/python.exe'
$artifactRoot = (Resolve-Path ..).Path
$openssl = 'C:/Program Files/Git/usr/bin/openssl.exe'
$opensslPin = (Get-FileHash -LiteralPath $openssl -Algorithm SHA256).Hash.ToLower()
$fixture = & $py -m strattester.research_cli prepare-walk-forward `
  --output (Join-Path $artifactRoot 'signed-walkforward-fixture') --openssl-exe $openssl `
  --openssl-sha256 $opensslPin --scratch-root $artifactRoot | ConvertFrom-Json
& $py -m strattester.research_cli walk-forward --enable-research `
  --source $fixture.source_path --source-sha256 $fixture.source_sha256 `
  --trust-store $fixture.trust_store_path --trust-store-sha256 $fixture.trust_store_sha256 `
  --checkpoint $fixture.checkpoint_path --checkpoint-sha256 $fixture.checkpoint_sha256 `
  --openssl-exe $openssl --openssl-sha256 $opensslPin --scratch-root $artifactRoot `
  --output (Join-Path $artifactRoot 'signed-walkforward-result')
```

The fixture's printed pins are public synthetic evidence only. In an independently
supplied dataset, provision the source, trust and bootstrap checkpoint pins through
an independent trusted channel. The externally pinned dataset contains an exact
schema: version/scope/label contract, ordered exports with per-manifest SHA256 and
complete policy, indexed labels with instrument/timeframe/end/return, structural
config, folds, holdout symbols, steps/seed/costs/embargo and explicit sequential
retraining policy. All file references inside it are ordinary relative filenames.
No connection strings or network clients are accepted.

For another instrument/timeframe contract, call `prepare_walkforward_fixture` with
`instruments`, `timeframes_ns` and `horizon_ns`; the horizon must divide into complete
timeframes. The consumer has no hardcoded exchange, symbol or timeframe. The fixture
builder deliberately bounds its sample contract to two or three distinct symbols
and one or two timeframes, with the final symbol held out from training and context.

Each origin first produces causal return/rolling-mean/volatility features and a
diagnostic prediction from the independently pinned bootstrap. Bootstrap predictions
never enter fold training or threshold selection. Each fold builds a fresh model,
purges cross-boundary labels, applies embargo, removes held-out targets and context
from training, fits controls on training only, then freezes its threshold on
validation before test evaluation. Prior OOS may enter a later fold's training or
validation only with explicit sequential retraining enabled. Test windows cannot
overlap. Reports label the folds sequential and make no pooled portfolio claim.

Every fold checkpoint is SHA256-verified, reloaded and checked against its exact
training-dataset fingerprint and seed. Replay predictions, distribution metrics and
fee/slippage ledgers must match training-time evaluation before publication.
`report.json` contains signed source receipts, bootstrap provenance, all fold
checkpoints' hashes, replay forecasts and ledger metrics. The ledger uses independent
round trips and charges entry and exit costs. Funding is explicitly BLOCKED because
signed funding event data is absent; the ledger excludes funding and cannot be
represented as funding-adjusted PnL. Availability at the synthetic origin is an
engineering convention, not a deployment latency measurement.

Admission limits include 4 MiB source JSON, 64 signed exports, 1,024 labels, 100,000
aggregate example bars, 32 folds, 1,000 optimizer steps per fold, conservative
512 MiB aggregate preparation, 8 MiB report and 64 MiB published output. These are
software admission bounds; native CPU/RSS/wall-time enforcement is not qualified.
Cancellation is checked during verification, preparation, training and replay.
Controlled failure/cancellation removes the private staging directory; retry uses a
new output directory. Existing output is never intentionally overwritten. An abrupt
process death can leave an unregistered `.walkforward-*` stage: preserve it for
inspection and rerun to a fresh destination; partial stages are never accepted as
completed reports. No production database, services, trading or physical G1 runs.
