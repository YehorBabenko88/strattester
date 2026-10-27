"""Independent point-in-time candle resampling oracle (synthetic only)."""
from decimal import Decimal

def aggregate_candles(rows, *, step_ns, factor, cutoff_ns):
    """Each row: (open_ns, close_ns, available_ns, O, H, L, C, volume).
    End is exclusive. Reject partial buckets, gaps, future availability.
    """
    if (type(step_ns) is not int or step_ns <= 0 or type(factor) is not int
            or factor <= 0 or type(cutoff_ns) is not int or cutoff_ns < 0
            or len(rows) != factor):
        raise ValueError("invalid aggregation configuration")
    first = rows[0][0]
    if type(first) is not int or first < 0 or first % (step_ns * factor):
        raise ValueError("misaligned aggregate open")
    parsed = []
    for i, row in enumerate(rows):
        if len(row) != 8:
            raise ValueError("invalid candle shape")
        start, end, available, o, h, l, c, volume = row
        if (any(type(t) is not int for t in (start, end, available))
                or start != first + i * step_ns or end != start + step_ns
                or available < end or available > cutoff_ns):
            raise ValueError("gap, open candle or future availability")
        values = tuple(Decimal(str(x)) for x in (o, h, l, c, volume))
        o, h, l, c, volume = values
        if (not all(v.is_finite() for v in values) or l <= 0 or volume < 0
                or not l <= o <= h or not l <= c <= h):
            raise ValueError("invalid OHLCV")
        parsed.append(values)
    return (first, first + factor * step_ns,
            parsed[0][0], max(x[1] for x in parsed),
            min(x[2] for x in parsed), parsed[-1][3],
            sum((x[4] for x in parsed), Decimal(0)))
