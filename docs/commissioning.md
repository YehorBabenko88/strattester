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
