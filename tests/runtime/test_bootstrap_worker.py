from strattester.runtime.bootstrap_worker import build_worker
def test_worker_bootstrap_has_durable_state(tmp_path):
    b,state,runtime=build_worker(tmp_path,lambda job:None)
    assert b.state_db.exists()
    assert runtime.state_store is state
    state.close()

from strattester.marketdata.sqlite_store import SQLiteMarketStore,Candle

def test_worker_bootstrap_wires_background_migration_for_existing_market_db(tmp_path):
    data=tmp_path/'data'; data.mkdir()
    market=data/'bybit_1m.sqlite3'
    store=SQLiteMarketStore.open(market)
    store.upsert_candles([Candle('BTCUSDT','1m',0,1,1,1,1,1)])
    store.close()
    b,state,runtime=build_worker(tmp_path,lambda job:None)
    assert len(runtime.background_tasks)==1
    symbols=list(runtime.background_tasks[0].symbol_provider())
    assert symbols==['BTCUSDT']
    state.close()


def test_worker_uses_discovered_legacy_market_db(tmp_path, monkeypatch):
    """
    Integration regression:
    bootstrap may discover a valid market database outside root/data.
    build_worker must use that resolved BootstrapResult.market_db rather
    than silently falling back to config.market_db.
    """
    from strattester import bootstrap as bootstrap_module
    from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()

    legacy = legacy_dir / "bybit_1m.sqlite3"

    store = SQLiteMarketStore.open(legacy)
    store.upsert_candles([
        Candle(
            "BTCUSDT",
            "1m",
            0,
            1,
            1,
            1,
            1,
            1,
        )
    ])
    store.close()

    root = tmp_path / "ProgramData" / "Strattester"

    # bootstrap() default argument captured LEGACY_PATHS when the function
    # was defined, therefore patch build_worker's bootstrap call with an
    # explicit controlled legacy path.
    original_bootstrap = bootstrap_module.bootstrap

    def controlled_bootstrap(worker_root):
        return original_bootstrap(
            worker_root,
            legacy_paths=(legacy,),
        )

    monkeypatch.setattr(
        "strattester.runtime.bootstrap_worker.bootstrap",
        controlled_bootstrap,
    )

    b, state, runtime = build_worker(
        root,
        lambda job: None,
    )

    try:
        assert b.mode == "legacy-readonly"
        assert b.market_db == legacy

        # Canonical configured DB must still not have been fabricated.
        assert not b.config.market_db.exists()

        # The discovered legacy DB must nevertheless be wired into the
        # worker's migration/background path.
        assert len(runtime.background_tasks) == 1

        symbols = list(
            runtime.background_tasks[0].symbol_provider()
        )

        assert symbols == ["BTCUSDT"]

    finally:
        runtime.close()


def test_worker_survives_legacy_disappearing_after_bootstrap(tmp_path, monkeypatch):
    """
    If an externally discovered legacy DB disappears after bootstrap,
    worker startup must degrade safely without fabricating a canonical DB.
    """
    from strattester import bootstrap as bootstrap_module
    from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle

    legacy = tmp_path / "legacy" / "bybit_1m.sqlite3"
    legacy.parent.mkdir()

    store = SQLiteMarketStore.open(legacy)
    store.upsert_candles([
        Candle("BTCUSDT", "1m", 0, 1, 1, 1, 1, 1)
    ])
    store.close()

    root = tmp_path / "ProgramData" / "Strattester"
    original_bootstrap = bootstrap_module.bootstrap

    def controlled_bootstrap(worker_root):
        result = original_bootstrap(
            worker_root,
            legacy_paths=(legacy,),
        )

        assert result.market_db == legacy
        legacy.unlink()

        return result

    monkeypatch.setattr(
        "strattester.runtime.bootstrap_worker.bootstrap",
        controlled_bootstrap,
    )

    b, state, runtime = build_worker(
        root,
        lambda job: None,
    )

    try:
        assert b.mode == "legacy-readonly"
        assert b.market_db == legacy
        assert not legacy.exists()
        assert not b.config.market_db.exists()
        assert runtime.background_tasks == []
    finally:
        runtime.close()


def test_worker_closes_state_if_legacy_open_fails(tmp_path, monkeypatch):
    """
    A legacy DB may become corrupt after bootstrap discovery.
    Startup must fail closed and release the already-opened state store.
    """
    import pytest

    from strattester import bootstrap as bootstrap_module
    import strattester.runtime.bootstrap_worker as worker_module
    from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle

    legacy = tmp_path / "legacy" / "bybit_1m.sqlite3"
    legacy.parent.mkdir()

    store = SQLiteMarketStore.open(legacy)
    store.upsert_candles([
        Candle("BTCUSDT", "1m", 0, 1, 1, 1, 1, 1)
    ])
    store.close()

    root = tmp_path / "ProgramData" / "Strattester"
    original_bootstrap = bootstrap_module.bootstrap

    def controlled_bootstrap(worker_root):
        result = original_bootstrap(
            worker_root,
            legacy_paths=(legacy,),
        )

        assert result.market_db == legacy

        # Simulate corruption after successful discovery.
        legacy.write_bytes(b"not-a-sqlite-database")

        return result

    monkeypatch.setattr(
        worker_module,
        "bootstrap",
        controlled_bootstrap,
    )

    real_open = worker_module.SQLiteStateStore.open
    opened_state = []

    def tracked_state_open(path):
        state = real_open(path)
        opened_state.append(state)
        return state

    monkeypatch.setattr(
        worker_module.SQLiteStateStore,
        "open",
        tracked_state_open,
    )

    with pytest.raises(Exception):
        worker_module.build_worker(
            root,
            lambda job: None,
        )

    # bootstrap() opens/closes state once to initialize the DB, then
    # build_worker() opens the runtime state store a second time.
    assert len(opened_state) == 2

    bootstrap_state = opened_state[0]
    runtime_state = opened_state[1]

    import sqlite3

    # Bootstrap's initialization handle must already be closed.
    with pytest.raises(sqlite3.ProgrammingError):
        bootstrap_state.con.execute("SELECT 1")

    # If later market-store initialization fails, the runtime state
    # handle must also be closed (transactional startup semantics).
    with pytest.raises(sqlite3.ProgrammingError):
        runtime_state.con.execute("SELECT 1")


def test_worker_constructor_failure_closes_all_partial_resources(tmp_path, monkeypatch):
    """
    If startup fails after the market backend has already been opened,
    every partially initialized resource must be closed before the
    original exception escapes.
    """
    import pytest
    import sqlite3

    import strattester.runtime.bootstrap_worker as worker_module
    from strattester.marketdata.sqlite_store import SQLiteMarketStore, Candle

    root = tmp_path / "ProgramData" / "Strattester"
    market = root / "data" / "bybit_1m.sqlite3"
    market.parent.mkdir(parents=True)

    seed = SQLiteMarketStore.open(market)
    seed.upsert_candles([
        Candle("BTCUSDT", "1m", 0, 1, 1, 1, 1, 1)
    ])
    seed.close()

    opened_state = []
    opened_market = {}

    real_state_open = worker_module.SQLiteStateStore.open
    real_market_open = worker_module.open_market_store

    def tracked_state_open(path):
        state = real_state_open(path)
        opened_state.append(state)
        return state

    def tracked_market_open(market_db, shards_dir):
        shards = real_market_open(market_db, shards_dir)
        opened_market["shards"] = shards
        opened_market["legacy"] = shards.legacy_store
        return shards

    class ConstructorFailure(RuntimeError):
        pass

    def fail_worker_runtime(*args, **kwargs):
        raise ConstructorFailure("synthetic WorkerRuntime constructor failure")

    monkeypatch.setattr(
        worker_module.SQLiteStateStore,
        "open",
        tracked_state_open,
    )

    monkeypatch.setattr(
        worker_module,
        "open_market_store",
        tracked_market_open,
    )

    monkeypatch.setattr(
        worker_module,
        "WorkerRuntime",
        fail_worker_runtime,
    )

    with pytest.raises(
        ConstructorFailure,
        match="synthetic WorkerRuntime constructor failure",
    ):
        worker_module.build_worker(
            root,
            lambda job: None,
        )

    # bootstrap() initializes state once, build_worker() opens it again.
    assert len(opened_state) == 2

    bootstrap_state = opened_state[0]
    runtime_state = opened_state[1]

    # Both SQLite state handles must be closed.
    with pytest.raises(sqlite3.ProgrammingError):
        bootstrap_state.con.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        runtime_state.con.execute("SELECT 1")

    legacy = opened_market["legacy"]

    # Legacy market connection must also be closed.
    with pytest.raises(sqlite3.ProgrammingError):
        legacy.connection.execute("SELECT 1")

    # Sharded backend must have released its own resources as well.
    # close() is intentionally safe/idempotent, so a second close must
    # not resurrect or damage anything.
    opened_market["shards"].close()
