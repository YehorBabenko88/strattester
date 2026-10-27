"""Independent timestamp watermark monotonicity oracle."""
def validate_watermark_sequence(watermarks):
    if not watermarks:
        raise ValueError("missing watermarks")
    last = -1
    for value in watermarks:
        if type(value) is not int or value < 0 or value < last:
            raise ValueError("invalid or regressing watermark")
        last = value
    return last

def validate_snapshot_cutoff(watermark_ns, cutoff_ns, latest_available_ns):
    if any(type(x) is not int or x < 0 for x in (watermark_ns,cutoff_ns,latest_available_ns)):
        raise ValueError("invalid timestamp")
    if watermark_ns > cutoff_ns or latest_available_ns > cutoff_ns:
        raise ValueError("future watermark or data")
    return True
