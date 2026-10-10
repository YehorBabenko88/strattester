from strattester.runtime.background_migration import BackgroundShardMigration
from strattester.engine.resource_manager import ResourceSnapshot

GB=1024**3
class Migrator:
    def __init__(self): self.calls=[]
    def migrate_batch(self,symbols,**kw):
        self.calls.append((list(symbols),kw)); return 'ok'

def test_background_migration_runs_only_with_normal_resource_headroom():
    m=Migrator()
    snap=lambda:ResourceSnapshot(16*GB,12*GB,100*GB,20,8)
    bg=BackgroundShardMigration(m,lambda:['BTCUSDT'],snap,5*GB,batch_symbols=2,interval_seconds=60)
    assert bg.maybe_run(now=100)=='ok'
    assert len(m.calls)==1
    assert bg.maybe_run(now=120) is None
    assert len(m.calls)==1
    assert bg.maybe_run(now=161)=='ok'
    assert len(m.calls)==2

def test_background_migration_pauses_under_cpu_ram_or_disk_pressure():
    for snap in (
        ResourceSnapshot(16*GB,12*GB,100*GB,95,8),
        ResourceSnapshot(16*GB,1*GB,100*GB,10,8),
        ResourceSnapshot(16*GB,12*GB,1*GB,10,8),
    ):
        m=Migrator()
        bg=BackgroundShardMigration(m,lambda:['BTCUSDT'],lambda s=snap:s,5*GB)
        assert bg.maybe_run(now=100) is None
        assert m.calls==[]


def test_background_failure_does_not_kill_worker(tmp_path):
    import logging

    from strattester.engine.scheduler import Scheduler
    from strattester.persistence.sqlite_state_store import SQLiteStateStore
    from strattester.runtime.lifecycle import Lifecycle
    from strattester.runtime.worker import WorkerRuntime

    class BrokenBackground:
        def __init__(self):
            self.calls = 0

        def maybe_run(self):
            self.calls += 1
            raise RuntimeError("synthetic background failure")

    task = BrokenBackground()
    state = SQLiteStateStore.open(tmp_path / "state.db")

    worker = WorkerRuntime(
        state,
        Scheduler(state),
        lambda job: None,
        Lifecycle(),
        logging.getLogger("test.background.failure"),
        lambda: ResourceSnapshot(16*GB, 12*GB, 100*GB, 10, 8),
        background_tasks=[task],
    )

    try:
        # Background failure is contained by WorkerRuntime.
        assert worker.run_once() == 0
        assert task.calls == 1

        # The worker remains usable on the next cycle.
        assert worker.run_once() == 0
        assert task.calls == 2
    finally:
        worker.close()
        state.close()


def test_background_migration_failure_uses_retry_backoff():
    """
    A failed migration advances next_run before the exception escapes.
    WorkerRuntime can log the failure without retrying on every poll.
    """
    class BrokenMigrator:
        def __init__(self):
            self.calls = 0

        def migrate_batch(self, symbols, **kwargs):
            self.calls += 1
            raise RuntimeError("legacy database unavailable")

    migrator = BrokenMigrator()

    bg = BackgroundShardMigration(
        migrator,
        lambda: ["BTCUSDT"],
        lambda: ResourceSnapshot(16*GB, 12*GB, 100*GB, 10, 8),
        5*GB,
        interval_seconds=60,
    )

    import pytest

    with pytest.raises(RuntimeError, match="legacy database unavailable"):
        bg.maybe_run(now=100)

    assert migrator.calls == 1

    assert bg.next_run == 160.0

    # Still inside the backoff window: no second migration attempt.
    assert bg.maybe_run(now=101) is None
    assert bg.maybe_run(now=159.999) is None
    assert migrator.calls == 1

    # At the retry boundary the migration is attempted again.
    with pytest.raises(RuntimeError, match="legacy database unavailable"):
        bg.maybe_run(now=160)

    assert migrator.calls == 2
    assert bg.next_run == 220.0


def test_failed_symbol_is_not_ready_and_can_retry_after_source_recovers(tmp_path):
    from strattester.marketdata.shard_manifest import ShardState
    from strattester.marketdata.shard_migrator import ShardMigrator

    class Manifest:
        def __init__(self):
            self.records = {}

        def ready(self, symbol):
            record = self.records.get(symbol)
            return record is not None and record.state is ShardState.SHARD_READY

        def get(self, symbol):
            return self.records.get(symbol)

        def set(self, symbol, state, rows_copied=0, error=None):
            class Record:
                pass

            record = Record()
            record.state = state
            record.rows_copied = rows_copied
            record.error = error
            self.records[symbol] = record

    class RecoveringStore:
        def __init__(self, root):
            self.root = root
            self.manifest = Manifest()
            self.available = False

        def migrate_legacy_candles(self, symbol, batch_size=20_000):
            if not self.available:
                raise OSError("legacy database temporarily unavailable")

            self.manifest.set(
                symbol,
                ShardState.SHARD_READY,
                rows_copied=3,
                error=None,
            )
            return 3

    store = RecoveringStore(tmp_path)
    migrator = ShardMigrator(store)

    failed = migrator.migrate_batch(
        ["BTCUSDT"],
        limit=1,
        min_free_bytes=1,
    )

    assert failed.attempted == 1
    assert failed.ready == 0
    assert failed.failed == 1
    assert not store.manifest.ready("BTCUSDT")
    assert store.manifest.get("BTCUSDT").state is ShardState.FAILED

    # Source becomes available again.
    store.available = True

    recovered = migrator.migrate_batch(
        ["BTCUSDT"],
        limit=1,
        min_free_bytes=1,
    )

    assert recovered.attempted == 1
    assert recovered.ready == 1
    assert recovered.failed == 0
    assert recovered.copied_rows == 3
    assert store.manifest.ready("BTCUSDT")
