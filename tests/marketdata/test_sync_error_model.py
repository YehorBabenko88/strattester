import pytest

from strattester.marketdata.bybit_client import (
    BybitAccessError,
    RetryableBybitError,
)
from strattester.marketdata.errors import (
    DatasetUnavailableError,
    MarketDataAccessError,
    RetryableMarketDataError,
    MarketDataIntegrityError,
)
from strattester.marketdata.sqlite_store import SQLiteMarketStore
from strattester.marketdata.sync_engine import (
    DataRequirement,
    SyncEngine,
    SyncState,
)


def run_error(tmp_path,exc):
    class Client:
        def fetch_open_interest(self,*args,**kwargs):
            raise exc

    store=SQLiteMarketStore.open(
        tmp_path / "market.db"
    )

    try:
        return SyncEngine(
            store,
            Client(),
            clock_ms=lambda:999999,
        ).sync_requirement(
            DataRequirement(
                "BTCUSDT",
                "open_interest",
                "5m",
                0,
                0,
            )
        )
    finally:
        store.close()


def test_typed_dataset_unavailable_is_unavailable(tmp_path):
    result=run_error(
        tmp_path,
        DatasetUnavailableError(
            "arbitrary provider wording"
        ),
    )

    assert result.state is SyncState.UNAVAILABLE


@pytest.mark.parametrize(
    "message",
    [
        "not supported",
        "not available for this symbol",
        "unsupported dataset",
        "DatasetUnavailableError",
        "NotSupportedError",
    ],
)
def test_magic_words_cannot_create_unavailable(
    tmp_path,
    message,
):
    result=run_error(
        tmp_path,
        RuntimeError(message),
    )

    assert result.state is SyncState.RETRYABLE


def test_fake_class_name_cannot_spoof_unavailable(tmp_path):
    FakeUnavailable=type(
        "DatasetUnavailableError",
        (RuntimeError,),
        {},
    )

    result=run_error(
        tmp_path,
        FakeUnavailable(
            "not available for this symbol"
        ),
    )

    assert result.state is SyncState.RETRYABLE


def test_typed_access_is_degraded(tmp_path):
    result=run_error(
        tmp_path,
        MarketDataAccessError(
            "access denied"
        ),
    )

    assert result.state is SyncState.DEGRADED


def test_existing_bybit_access_remains_degraded(tmp_path):
    result=run_error(
        tmp_path,
        BybitAccessError(
            "forbidden"
        ),
    )

    assert result.state is SyncState.DEGRADED


def test_typed_retryable_is_retryable(tmp_path):
    result=run_error(
        tmp_path,
        RetryableMarketDataError(
            "temporary failure"
        ),
    )

    assert result.state is SyncState.RETRYABLE


def test_integrity_error_is_retryable_fail_closed(tmp_path):
    result=run_error(
        tmp_path,
        MarketDataIntegrityError(
            "malformed provider data"
        ),
    )

    assert result.state is SyncState.RETRYABLE


def test_existing_bybit_retryable_remains_retryable(tmp_path):
    result=run_error(
        tmp_path,
        RetryableBybitError(
            "temporary HTTP failure"
        ),
    )

    assert result.state is SyncState.RETRYABLE


def test_unknown_exception_is_retryable(tmp_path):
    result=run_error(
        tmp_path,
        LookupError(
            "unexpected failure"
        ),
    )

    assert result.state is SyncState.RETRYABLE
