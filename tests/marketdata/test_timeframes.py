import pytest

from strattester.marketdata.timeframes import (
    aligned_window,
    align_end_ms,
    align_start_ms,
    expected_points,
    timeframe_ms,
)


@pytest.mark.parametrize(
    "timeframe,expected",
    [
        ("1m",60_000),
        ("3m",180_000),
        ("5m",300_000),
        ("15m",900_000),
        ("1h",3_600_000),
        ("4h",14_400_000),
        ("1d",86_400_000),
        ("480m",28_800_000),
        ("8h",28_800_000),
    ],
)
def test_timeframe_ms(timeframe,expected):
    assert timeframe_ms(timeframe)==expected


@pytest.mark.parametrize(
    "timeframe",
    [
        "",
        "x",
        "0m",
        "-1m",
        "1w",
        "abc",
    ],
)
def test_invalid_timeframe_fails_closed(timeframe):
    with pytest.raises(ValueError):
        timeframe_ms(timeframe)


def test_alignment_ceil_start_floor_end():
    assert align_start_ms(
        60_001,
        300_000,
    ) == 300_000

    assert align_end_ms(
        599_999,
        300_000,
    ) == 300_000


def test_window_with_one_real_5m_point():
    assert aligned_window(
        60_000,
        360_000,
        "5m",
    ) == (
        300_000,
        300_000,
    )

    assert expected_points(
        60_000,
        360_000,
        "5m",
    ) == 1


def test_window_without_complete_point_is_none():
    assert aligned_window(
        60_000,
        179_999,
        "5m",
    ) is None

    assert expected_points(
        60_000,
        179_999,
        "5m",
    ) == 0


def test_delisting_boundary_never_rounds_forward():
    assert aligned_window(
        0,
        179_999,
        "1m",
    ) == (
        0,
        120_000,
    )


def test_resume_boundary_never_rounds_backward():
    assert aligned_window(
        240_001,
        600_000,
        "5m",
    ) == (
        300_000,
        600_000,
    )
