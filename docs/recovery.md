# Recovery

Durable jobs use explicit states and leases. A stale RUNNING/LEASED job becomes RETRYABLE; worker disappearance alone never marks a job COMPLETE.

Remote code activation uses a staged immutable release. A failed health check restores the previous known-good release marker. Runtime data directories are outside the release tree.
