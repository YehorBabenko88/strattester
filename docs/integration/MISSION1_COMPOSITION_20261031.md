# Historical consumer composition

Base: source-owner sealed receipt restoration `931f85f` on the newer data-first/F1 runtime. Selective additive imports come from `8a9f31fa7d07f9201edadc2d2ff94a5e3e1c75a5`, the display-fix descendant of history consumer `c951b3f711780affc8e6936f75fe3796d8ef99eb`. `mission1-composition-provenance.json` records original and current file hashes. One reviewed security adaptation disables Git replacement objects centrally in MathClient.git; disposable-repository tests prove both default and environment-selected replacement namespaces cannot change staged pinned worker bytes. No existing execution, data-first, financial, F1, lifecycle or sealed owned-run implementation is replaced.

The optional offline path consumes Grid immutable v1.1 envelopes; MathClient launches pinned timed Math processes; Strattester replay evaluates frozen strategies with chronological train/validation/test, explicit fees/slippage/funding and producer-owned result receipts. Review and handoff adapters preserve observed event clocks separately from source availability, forecast decisions and declared publication. JointMathClient runs the timed and scientific APIs from one committed Math tree and captures its exact request. The display adapter binds the scientific response to the same dataset, source, model and historical forecast before exporting `terminan.unified-display.v1`.

Replay receipts, sealed owned-run records, source receipt hashes and display hashes are distinct versioned contracts. This composition does not turn one into another or fabricate COMPLETE state. Original branch reference-pin documents remain archival evidence; the coordinated release manifest is managed separately after review.

`test_composed_history_runtime.py` exercises actual pinned Math processes using explicitly synthetic Grid fixture records, requires nonempty held-out simulated trades, and checks the actual scientific series and frozen forecast. A deterministic gapped tape is used to exercise held-out execution; this is not evidence of profitability. The generated packet stays SYNTHETIC / UNATTESTED / NOT_QUALIFIED, contract_only true and all training/execution/trading authority flags false. Real historical source admission, model promotion, physical Windows qualification and live orders remain outside this test.

Run cross-repository verification with explicit clean source paths:

```sh
GRID_REFERENCE=/path/to/grid MATH_REFERENCE=/path/to/math TERMINAN_REFERENCE=/path/to/Terminan HISTORY_REQUIRE_CROSSREPO=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -m pytest
```

The original consumer tests provision Grid on their import path. An isolated positive-test invocation also needs the Grid package on PYTHONPATH. Math refuses dirty source or wrong commit/tree/runtime pins. A temporary clean local clone can test the exact committed source while another developer edits their checkout; tests must never disable that refusal.
