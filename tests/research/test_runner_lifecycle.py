from types import SimpleNamespace

import pytest

from strattester.marketdata.instruments import (
    InstrumentRegistry,
    InstrumentStatus,
)
from strattester.research.runner import (
    LifecycleWindowError,
    _research_window,
)


def instrument(
    symbol="XUSDT",
    launch=0,
    delivery=None,
):
    result={
        "symbol":symbol,
        "launchTime":str(launch),
    }

    if delivery is not None:
        result["deliveryTime"]=str(delivery)

    return result


def test_without_registry_preserves_active_runner_contract():
    assert _research_window(
        instrument(),
        0,
        120_000,
    ) == (
        0,
        120_000,
    )


def test_exchange_delivery_time_clips_without_registry():
    assert _research_window(
        instrument(
            symbol="OLDUSDT",
            delivery=120_000,
        ),
        0,
        300_000,
    ) == (
        0,
        120_000,
    )


def test_registry_clips_request_at_actual_delisting_boundary(
    tmp_path,
):
    registry=InstrumentRegistry.open(
        tmp_path / "registry.db"
    )

    registry.reconcile(
        {"OLDUSDT"},
        0,
    )

    registry.reconcile_lifecycle(
        set(),
        {
            "OLDUSDT":
            InstrumentStatus.DELISTED
        },
        {
            "OLDUSDT":180_000
        },
        300_000,
    )

    assert _research_window(
        instrument("OLDUSDT"),
        0,
        600_000,
        registry,
    ) == (
        0,
        179_999,
    )

    registry.close()


def test_delisting_boundary_survives_reboot(
    tmp_path,
):
    path=tmp_path / "registry.db"

    registry=InstrumentRegistry.open(path)

    registry.reconcile(
        {"OLDUSDT"},
        0,
    )

    registry.close()

    # Machine was offline during actual delisting.
    registry=InstrumentRegistry.open(path)

    registry.reconcile_lifecycle(
        set(),
        {
            "OLDUSDT":
            InstrumentStatus.DELISTED
        },
        {
            "OLDUSDT":180_000
        },
        600_000,
    )

    registry.close()

    reopened=InstrumentRegistry.open(path)

    assert _research_window(
        instrument("OLDUSDT"),
        0,
        900_000,
        reopened,
    ) == (
        0,
        179_999,
    )

    reopened.close()


def test_suspension_resume_cannot_be_silently_stitched(
    tmp_path,
):
    registry=InstrumentRegistry.open(
        tmp_path / "registry.db"
    )

    registry.reconcile(
        {"XUSDT"},
        0,
    )

    registry.set_status(
        "XUSDT",
        InstrumentStatus.SUSPENDED,
        120_000,
    )

    registry.reconcile(
        {"XUSDT"},
        240_000,
    )

    assert registry.intervals(
        "XUSDT"
    ) == [
        (0,120_000),
        (240_000,None),
    ]

    with pytest.raises(
        LifecycleWindowError,
        match="segmented backtest required",
    ):
        _research_window(
            instrument("XUSDT"),
            0,
            360_000,
            registry,
        )

    registry.close()


def test_request_starting_inside_suspension_is_rejected(
    tmp_path,
):
    registry=InstrumentRegistry.open(
        tmp_path / "registry.db"
    )

    registry.reconcile(
        {"XUSDT"},
        0,
    )

    registry.set_status(
        "XUSDT",
        InstrumentStatus.SUSPENDED,
        120_000,
    )

    registry.reconcile(
        {"XUSDT"},
        240_000,
    )

    with pytest.raises(
        LifecycleWindowError,
        match="begins outside ACTIVE lifecycle",
    ):
        _research_window(
            instrument("XUSDT"),
            180_000,
            360_000,
            registry,
        )

    registry.close()


def test_request_inside_second_active_interval_is_allowed(
    tmp_path,
):
    registry=InstrumentRegistry.open(
        tmp_path / "registry.db"
    )

    registry.reconcile(
        {"XUSDT"},
        0,
    )

    registry.set_status(
        "XUSDT",
        InstrumentStatus.SUSPENDED,
        120_000,
    )

    registry.reconcile(
        {"XUSDT"},
        240_000,
    )

    assert _research_window(
        instrument("XUSDT"),
        240_000,
        360_000,
        registry,
    ) == (
        240_000,
        360_000,
    )

    registry.close()


def test_prelaunch_symbol_has_no_backtest_window(
    tmp_path,
):
    registry=InstrumentRegistry.open(
        tmp_path / "registry.db"
    )

    registry.reconcile_lifecycle(
        set(),
        {
            "NEWUSDT":
            InstrumentStatus.PRE_LISTING
        },
        {},
        100_000,
    )

    with pytest.raises(
        LifecycleWindowError,
        match="no ACTIVE lifecycle interval",
    ):
        _research_window(
            instrument("NEWUSDT"),
            0,
            300_000,
            registry,
        )

    registry.close()
