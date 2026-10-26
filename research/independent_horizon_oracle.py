"""Independent numeric target-horizon oracle with exclusive candle boundaries."""
from decimal import Decimal, localcontext

def horizon_target(bars, origin_index, horizon):
    """Bars are (open_ns, end_ns, close, available_ns)."""
    if (type(origin_index) is not int or type(horizon) is not int
        or horizon < 1 or origin_index < 0 or origin_index + horizon >= len(bars)):
        raise ValueError("invalid target horizon")
    previous_end = None
    for start, end, close, available in bars[:origin_index+horizon+1]:
        if (any(type(x) is not int or x < 0 for x in (start,end,available))
            or start >= end or available < end
            or (previous_end is not None and start != previous_end)):
            raise ValueError("gap or invalid candle")
        previous_end = end
        p = Decimal(str(close))
        if not p.is_finite() or p <= 0:
            raise ValueError("invalid price")
    origin = bars[origin_index]
    target = bars[origin_index+horizon]
    with localcontext() as ctx:
        ctx.prec = 70
        p0, p1 = Decimal(str(origin[2])), Decimal(str(target[2]))
        return {'origin_available_ns':origin[3], 'target_available_ns':target[3],
                'log_return':p1.ln()-p0.ln(), 'simple_return':p1/p0-1}
