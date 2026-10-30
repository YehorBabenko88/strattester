# Inert display export on top of #66

The history review now carries actual market separately from source identity.
Handoff retains model/version, units, split receipts, observations, frozen
forecast clocks/digests and original source fingerprints. An existing declared
publication is preserved; optional CLI --published-at-ms can supply it only
when not conflicting. OOS publication cannot precede test end, source
availability or forecast decisions. Without a publication clock, no OOS time
is invented. Old raw replay exports remain readable; an old review that lost
its market is rejected rather than assigned a guessed symbol.

`scripts/export_joint_display.py --history ... --joint-request ...
--joint-result ... --joint-receipt-pin ... --joint-published-at-ms ... --output ...`
wraps already produced records in `terminan.unified-display.v1` with explicit
contract_only/NOT_QUALIFIED and false authority. No engine or database is opened.
It preserves the original request/result and completion receipt, verifies
dataset/source/prefix/model identity against the historical handoff, and writes
exclusively to a new bounded file. Numerical algorithms remain in Math and
economic scoring remains in Strattester replay. Source authenticity is UNATTESTED.

JointMathClient now captures the original `joint_request` in its returned
receipt and freezes its graph/manifest independently from caller/client state.
The display CLI can use that captured request directly; --joint-request remains
available for older records and must match the capture when both exist.

Pure tests use literal wire records and a recorded qualified legacy replay
artifact from Terminan #59 CI41082077112. Those fixtures do not claim a new
Unified numerical run. New .github/workflows/display-handoff-contracts.yml runs
only these tests and emits exact-head evidence. Existing source pins remain
unchanged; Math #105 hosted gate and final combined E2E are still required.
