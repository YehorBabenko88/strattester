# Physical cluster commissioning

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
