"""Strict UTC integer timestamp unit conversion reference."""
MULTIPLIERS = {'s': 1_000_000_000, 'ms': 1_000_000, 'us': 1_000, 'ns': 1}

def convert_timestamp(value, source, target):
    if type(value) is not int or value < 0 or source not in MULTIPLIERS or target not in MULTIPLIERS:
        raise ValueError("invalid timestamp or unit")
    ns = value * MULTIPLIERS[source]
    divisor = MULTIPLIERS[target]
    if ns % divisor:
        raise ValueError("lossy timestamp conversion")
    return ns // divisor
