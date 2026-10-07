# Windows cluster commissioning

The commissioning scripts make adding Windows workers repeatable without copying private SSH keys.

## New node

Run elevated PowerShell on the new computer:

    .\ops\bootstrap-node.ps1 -Role Worker -InstallTailscale -InstallGit -ControlPublicKey '<CONTROL PUBLIC KEY>'

If Tailscale was just installed, authenticate interactively with `tailscale up`. Authentication credentials and private SSH keys must never be committed.

ESET remains a separate security layer. Allow inbound TCP/22 only from trusted Tailscale peers (the current commissioning baseline uses 100.64.0.0/10 plus Tailscale access controls). Do not disable ESET.

## Control host

Keep node metadata in a local copy of `ops/cluster-nodes.example.json` and run:

    .\ops\commission-cluster.ps1 -Inventory .\ops\cluster-nodes.example.json

This checks TCP/22 and passwordless SSH from the control host and fails closed when a node is unreachable.

## Tailscale policy automation

Do not automate policy changes by browser clicks. Prefer Tailscale grants/tags and an API-managed policy. API credentials must be supplied at runtime from a secret store/environment and must never be stored in this repository, inventory JSON, logs, or command history.

The scripts intentionally do not auto-expand tailnet access yet: changing authorization policy is a security-sensitive operation and must use a dedicated least-privilege credential plus validation/rollback. A future policy adapter should be explicit opt-in, validate the existing policy before mutation, use role tags rather than stable IP assumptions, and abort on conflicts.

## Roles

Network reachability does not grant Brain/voter/control authority. A newly commissioned node starts as a worker candidate and must pass application preflight before membership changes.


---

# Production commissioning gates

Production must not start directly after installation. A new or rebuilt fleet passes these gates in order; every gate is fail-closed and recorded durably.

1. INFRASTRUCTURE - Grid installed; nodes enrolled; a new node can join without application-code edits; node IDs are unique.
2. NODE_CONNECTIVITY - bidirectional Tailscale reachability, identity, latency and reconnect after reboot.
3. CONTROL_PLANE - coordinator/failover discovery, heartbeats, dynamic join/leave and scheduler redistribution.
4. DATABASE - PostgreSQL connectivity from every node, read/write probe, rollback, reconnect and fencing. SQLite stays node-local.
5. STORAGE - disk/RAM thresholds, WAL integrity, shard directories and permissions.
6. DATA_TRANSFER - a small checksummed payload is transferred and verified end-to-end.
7. TELEGRAM - command receive, authorization, reply, duplicate protection and outage recovery.
8. MINI_DATA - download a deliberately small symbol/time window into commissioning storage.
9. MINI_BACKTEST - run a deterministic small strategy batch on multiple nodes and compare outputs.
10. FAILURE_RECOVERY - reboot/kill a worker, interrupt network/DB, and join/leave nodes while test jobs exist.
11. CLEAN_RESET - stop services and delete only commissioning jobs/data/results/logs; production paths remain empty.
12. PRODUCTION_READY - recreate clean production stores, rerun read-only preflight, then allow historical bootstrap.

## Isolation rule

Commissioning uses a dedicated root such as C:/ProgramData/Strattester-Commissioning and a dedicated PostgreSQL database/schema. Never point commissioning at the future production market DB or ResultStore. CLEAN_RESET succeeds only when test artifacts are gone and no production artifact was touched.

## Dynamic nodes

Fleet membership is not a fixed PC list. Grid enrollment establishes stable node identity and heartbeat. Scheduling uses the current live-node set and resource snapshots: joining adds capacity, leaving removes capacity, and leased work is recovered through fencing/CAS. Strategy and market-data code must not branch on PC1/PC2 names.
