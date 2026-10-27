"""Independent time/unit/candle aggregation oracles. No producer imports."""
from decimal import Decimal

NS_PER_MS = 1_000_000

def ms_to_ns(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid millisecond timestamp")
    return value * NS_PER_MS

def ns_to_ms_exact(value):
    if type(value) is not int or value < 0 or value % NS_PER_MS:
        raise ValueError("nonintegral millisecond timestamp")
    return value // NS_PER_MS

def validate_candle(open_ns, close_ns, available_ns, cutoff_ns, watermark_ns):
    values = (open_ns, close_ns, available_ns, cutoff_ns, watermark_ns)
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError("invalid timestamp")
    if not (open_ns < close_ns <= available_ns <= cutoff_ns and close_ns <= watermark_ns <= cutoff_ns):
        raise ValueError("open, unavailable or unwatermarked candle")
    return True

def aggregate_closed_bars(bars, step_ns, cutoff_ns, watermark_ns):
    """bars: (open_ns, close_ns, O, H, L, C, volume, available_ns)."""
    if type(step_ns) is not int or step_ns <= 0 or not bars:
        raise ValueError("invalid step/bars")
    previous = None
    volume = Decimal(0)
    for i, (start, end, o, h, l, c, v, available) in enumerate(bars):
        if end - start != step_ns or (previous is not None and start != previous):
            raise ValueError("gap, overlap or inconsistent timeframe")
        validate_candle(start, end, available, cutoff_ns, watermark_ns)
        o, h, l, c, v = map(lambda x: Decimal(str(x)), (o, h, l, c, v))
        if not all(x.is_finite() for x in (o, h, l, c, v)) or l <= 0 or v < 0 or not l <= o <= h or not l <= c <= h:
            raise ValueError("invalid OHLCV")
        if i == 0:
            first_open = o
            highest = h
            lowest = l
        highest = max(highest, h)
        lowest = min(lowest, l)
        volume += v
        last_close = c
        previous = end
    return (first_open, highest, lowest, last_close, volume)
