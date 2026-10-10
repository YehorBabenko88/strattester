# Recovery

Durable jobs use explicit states and leases. A stale RUNNING/LEASED job becomes RETRYABLE; worker disappearance alone never marks a job COMPLETE.

Remote code activation uses a staged immutable release. A failed health check restores the previous known-good release marker. Runtime data directories are outside the release tree.

Expired jobs remain scheduler candidates even when no separate READY job exists.
The scheduler never persists recovered snapshots: transactional claiming reloads
the job and rechecks any concurrent lease renewal before taking ownership.

An operator STOP persists `state/worker-intent.json` before stopping the worker.
Guardian respects this hold across its own restart. STOP also changes the worker
service to manual startup so a reboot cannot undo the hold. Explicit START
restores automatic startup and clears the hold. RESTART waits for SCM STOPPED
before issuing START; native command failures are reported instead of success.
Uninstallation removes Guardian before the controller and worker.

Controller and Guardian serialize worker intent plus SCM operations through a
SQLite OS lock in `state/worker-control.sqlite3`; a process crash releases the
lock. This prevents an in-flight guardian repair from restarting the worker
after STOP has completed. Failed lifecycle commands return an explicit failure
reply while the controller remains available for status and recovery commands.
