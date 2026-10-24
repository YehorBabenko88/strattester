"""Independent simple-return cash ledger oracle; NOT a portfolio simulator."""
from decimal import Decimal

def independent_roundtrip_ledger(rows, fee_bps=0, slippage_bps=0, funding_bps=0):
    costs = [Decimal(str(x)) for x in (fee_bps, slippage_bps, funding_bps)]
    if any(not x.is_finite() or x < 0 for x in costs) or not rows:
        raise ValueError("invalid costs or ledger")
    output = []
    previous = {}
    for instrument, start, end, simple_return, position in sorted(rows, key=lambda r:(r[1],r[0])):
        r = Decimal(str(simple_return))
        if (not isinstance(instrument,str) or not instrument
            or type(start) is not int or type(end) is not int or start < 0 or end <= start
            or start < previous.get(instrument,-1)
            or type(position) is not int or position not in (-1,0,1)
            or not r.is_finite() or r < -1):
            raise ValueError("invalid or overlapping trade")
        previous[instrument] = end
        gross = Decimal(position) * r
        turnover = Decimal(2 * abs(position))
        net = gross - turnover * (costs[0] + costs[1]) / 10000 - Decimal(abs(position)) * costs[2] / 10000
        output.append(net)
    return tuple(output)
