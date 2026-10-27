# Prepare-only Windows offline runner package

PHYSICAL_G1_AUTHORIZATION_RECOMMENDATION: **NOT_AUTHORIZED**
Trading: **NO-GO**. Native Windows controls: **NOT_RUN**.
This package cannot launch a model, install software, or modify a host.
A package hash proves bytes, not owner authorization or isolation.

## G0 commands (repository checkout, existing environment only)

```powershell
../financial-venv/Scripts/python.exe scripts/prepare_windows_offline_package.py --output work/windows-offline-plan.zip
Get-FileHash -Algorithm SHA256 work/windows-offline-plan.zip
../financial-venv/Scripts/python.exe -m pytest tests/research/test_financial_filesystem_security.py --basetemp=work/windows-filesystem-g0 -q
```

G0 packaging and portable filesystem checks do not establish G1 readiness.
Do not run this package on live nodes. No service, account, firewall, ACL,
production database, broker or default strategy changes are authorized.

## Disposable G1 plan — blocked design, no launch command

Use a disposable Windows VM with no production mounts, secrets, credentials,
broker keys or shared writable folders. An independent reviewer must inspect
an exact owner-signed plan binding the VM identity, expiry, source commit,
package SHA256, executable SHA256, snapshot/checkpoint SHA256, trusted producer
receipt, exact command, paths, caps and cleanup steps. A colocated checksum or
caller-supplied signature status cannot authorize execution. Signature trust
must be pinned independently; signature verification is currently NOT_RUN.

Before any child starts, a reviewed native launcher must enforce and attest:

- OS deny-all outbound and inbound networking, including IPv4, IPv6, DNS,
  loopback and child processes. Probe failures must be observed outside the
  child. Python socket patches are not an OS boundary.
- Restricted token with privileges removed, no elevation, no inherited host
  handles and no ability to change network or filesystem policy.
- Native handle-based confinement: reject every reparse point, junction,
  device path, ADS and namespace substitution; immutable read-only input
  handles and an empty dedicated writable output directory. Portable path
  checks retain TOCTOU gaps and are insufficient for this boundary.
- A job object assigned before child execution: kill-on-close, one process,
  2 GiB job memory, one CPU, 60 seconds wall time, 30 seconds CPU time,
  64 MiB output maximum. Reject launch if any cap cannot be enforced.

Trial scope: one synthetic snapshot, one reviewed CPU checkpoint, batch=1,
N<=32, channels<=16, recycles<=1; no training, GPU, downloads or real OOS claim.
No input may be substituted after signature validation. Start suspended,
attach enforced controls, then resume. Missing native control or evidence
means BLOCKED and no resume. The current repository has no such launcher.
All these controls therefore remain NOT_RUN, even if an owner signs a plan.

STOP immediately on outbound traffic, unexpected process/file access,
policy verification failure, hash/identity change, timeout, quota breach,
cancellation, partial output or missing provenance. Kill the entire job,
retain quarantined diagnostics, never publish READY, and label the result
BLOCKED/FAIL. Record exact SHA, executable/dependency inventory, signed plan,
input/output hashes, OS identity, native policy evidence and exit reason.

Cleanup: close job handles to terminate descendants; verify no remaining
processes; export only bounded diagnostic evidence to a separate quarantine;
destroy the disposable VM and its virtual disks. Do not roll back policies
on a live host because no live-host policy change is part of this plan.
Independent verification of cleanup is mandatory before any further trial.
