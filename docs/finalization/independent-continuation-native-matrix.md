# Read-only native component audit: launch remains refused

Baseline: PR21 `c09592be649d249c6b082a5e21cbeea2800a0049`, tree
`a31bd16e8826f92e12a5211360c4d926e7f09673`. This cycle changes no file under
`native/windows`. Code inspection is not new native execution evidence. The
stopped experimental implementation/review is not resumed or bypassed.

| Guarantee | Current reachable implementation | Missing proof / disposition |
|---|---|---|
| Owner signature | `OwnerIntent.Verify`: exact schema/domain, independently pinned Ed25519 resource and externally pinned raw owner public key | No provisioned owner trust registry, revocation/rotation/rollback protocol, or admitted research execution bridge. Pin provisioning is an external trust boundary. BLOCKED for execution. |
| Exact identities | Measured executable, input/package retained handles, source/tree build constants, local VM hash, limits/expiry | Local MachineGuid/SMBIOS/name measurement is not hardware/cloud attestation. Owner must independently bind the intended VM. |
| Expiry | Initial and final freshness check; monotonic elapsed-time maximum; `RemainingMilliseconds` | Actual research runtime does not call an admitted launch bridge. Pre-resume recheck and expiry-bounded job lifetime remain unqualified. |
| Durable nonce | `OwnerNonce.Claim`: relative NTFS create, pinned ancestry/security, flush, empty tombstone and final receipt, replay refusal | No connection from verified owner plan to an actual research launch. Storage rollback, VM snapshot restore, hostile administrator and physical power-loss durability remain outside proof. Never delete consumed receipts to permit replay. |
| Input handles | `LockedInput.Open` and `HandleComponent`: reject noncanonical/reparse/hardlink inputs; explicit owned-probe handle list | Complete interpreter/dependency/output namespace confinement and hostile namespace lifetime not established for research. BLOCKED. |
| Suspended admission | Owned component probe starts suspended, joins a queried Job Object before resume | Querying owned-probe settings does not establish actual research process restrictions. No research resume is admitted. |
| CPU/RAM/process limits | Job component configures and queries CPU rate, memory, process count and CPU time | Full actual-workload ceilings, child lifecycle, wall clock, cancellation, OOM and crash containment remain unqualified. |
| Networking | Existing component experiment tests owned direct TCP WFP baseline/block/recovery | DNS service/proxy, UDP, all IPv4/IPv6, loopback, descendants and handles to network-capable services not fully qualified. BLOCKED. |
| Output/cleanup | Bounded nonce cleanup manifest; no recursive receipt deletion | Research output byte limit, partial publication, crash/timeout cleanup and executable transport are not implemented as an admitted sandbox path. BLOCKED. |
| Default refusal | `Broker.Main --launch` returns78 before research process creation; diagnostics state missing controls | Required refusal remains in force. A signature/component receipt is never a G1 authorization. |

## Independent physical acceptance still required

The owner must first identify a fresh disposable VM and obtain read-only G0:
identity, OS/build, CPU/RAM/disk/GPU/driver, Python/dependencies, service and port
inventory, ACL/path boundaries and exact source/binary/input hashes. No LS5/PC4
inventory or active-host changes were performed in this cycle.

Independent QA must then establish each missing guarantee above, with positive
controls and explicit native failures/skips, against one exact binary. Missing
controls or evidence stop admission before resume. Only a separately signed,
exact, expiring owner authorization can permit the specified disposable G1;
there is no automatic authorization from software CI.

Current acceptance: `WINDOWS_SANDBOX_READINESS=BLOCKED`,
`PHYSICAL_G1=NOT_AUTHORIZED`, `TRADING=NO-GO`. No change to active services,
production databases, main or the stopped experimental source branch.

## Other confirmed findings in this cycle

* P1 fixed: the shipped public software producer key could authenticate a
  relabelled real-research scope when expected policy IDs/engine were changed.
  Reject its bytes independently of aliases. Synthetic use remains explicit.
* P1 fixed: Git replacement refs substituted source blob bytes while source/tree
  IDs remained original. Build object reads now disable replacement refs.
* P2 fixed: session publication hashed its previous receipt on replay.
* P2 fixed: checkpoint reconstruction consumed caller CPU RNG on successful and
  rejected loads. CPU state is preserved; `fork_rng` is not thread isolation.
* P2 fixed: cancellation was not checked during retained-row/revision validation.
* Remaining: concurrent threaded RNG users require serialization or separate
  processes. Numerical admission is not an enforced OS memory/RSS guarantee.

Real Grid first availability/revision/coherent producer epochs, authenticated
funding schedules, real OOS, real GPU and full upstream equivalence remain
external blockers. The new funding event API is software-only, fixed-entry-
notional accounting; it does not supply producer authentication or exchange fills.
