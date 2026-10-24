"""Reference for exclusive candle close and inclusive exchange last-trade timestamp."""
from research.independent_timestamp_units import convert_timestamp

def inclusive_last_ms_to_exclusive_end_ns(last_ms):
    if type(last_ms) is not int or last_ms < 0:
        raise ValueError("invalid inclusive last millisecond")
    return convert_timestamp(last_ms + 1, 'ms', 'ns')

def validate_bucket_alignment(open_ns, end_ns, timeframe_ns):
    if any(type(x) is not int for x in (open_ns,end_ns,timeframe_ns)) or open_ns < 0 or timeframe_ns <= 0:
        raise ValueError("invalid candle")
    if open_ns % timeframe_ns or end_ns - open_ns != timeframe_ns:
        raise ValueError("misaligned candle interval")
    return True
