# Remote administration

Strattester does not require Tailscale to run.

Normal remote lifecycle is GitHub release/commit -> staged release -> validation -> drain -> activation -> health check -> automatic rollback on failure.

Tailscale is an optional private administration path for RDP/SSH/diagnostics. Do not expose Strattester administration directly to the public Internet and do not commit Tailscale auth keys or Telegram tokens.

Runtime data lives outside release directories, so code deployment must not replace `data/`, `state/`, `results/`, or `logs/`.
