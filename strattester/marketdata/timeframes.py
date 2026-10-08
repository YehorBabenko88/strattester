from __future__ import annotations


_TIMEFRAME_MS={
    '1m':60_000,
    '3m':180_000,
    '5m':300_000,
    '15m':900_000,
    '30m':1_800_000,
    '1h':3_600_000,
    '2h':7_200_000,
    '4h':14_400_000,
    '6h':21_600_000,
    '12h':43_200_000,
    '1d':86_400_000,
}


def timeframe_ms(timeframe:str)->int:
    tf=str(timeframe).strip().lower()

    if tf in _TIMEFRAME_MS:
        return _TIMEFRAME_MS[tf]

    if len(tf)<2:
        raise ValueError(
            f'unsupported timeframe: {timeframe!r}'
        )

    unit=tf[-1]

    try:
        value=int(tf[:-1])
    except ValueError as exc:
        raise ValueError(
            f'unsupported timeframe: {timeframe!r}'
        ) from exc

    if value<=0:
        raise ValueError(
            f'timeframe must be positive: {timeframe!r}'
        )

    multipliers={
        'm':60_000,
        'h':3_600_000,
        'd':86_400_000,
    }

    if unit not in multipliers:
        raise ValueError(
            f'unsupported timeframe: {timeframe!r}'
        )

    return value*multipliers[unit]


def align_start_ms(timestamp:int,step_ms:int)->int:
    timestamp=int(timestamp)
    step_ms=int(step_ms)

    if step_ms<=0:
        raise ValueError('step_ms must be positive')

    return (
        (timestamp+step_ms-1)
        // step_ms
    )*step_ms


def align_end_ms(timestamp:int,step_ms:int)->int:
    timestamp=int(timestamp)
    step_ms=int(step_ms)

    if step_ms<=0:
        raise ValueError('step_ms must be positive')

    return (
        timestamp
        // step_ms
    )*step_ms


def aligned_window(
    start_ms:int,
    end_ms:int,
    timeframe:str,
):
    step=timeframe_ms(timeframe)

    start=align_start_ms(
        start_ms,
        step,
    )

    end=align_end_ms(
        end_ms,
        step,
    )

    if start>end:
        return None

    return start,end


def expected_points(
    start_ms:int,
    end_ms:int,
    timeframe:str,
)->int:
    window=aligned_window(
        start_ms,
        end_ms,
        timeframe,
    )

    if window is None:
        return 0

    start,end=window
    step=timeframe_ms(timeframe)

    return (
        (end-start)
        // step
    )+1
