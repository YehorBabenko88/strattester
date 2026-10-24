"""Independent instrument/timeframe identity invariance oracle."""
def validate_series_identity(rows):
    """rows: (venue, market_type, symbol, timeframe, open_ns, end_ns)."""
    if not rows:
        raise ValueError("empty series")
    identities = set()
    seen = set()
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=6:
            raise ValueError("invalid series row")
        venue,market,symbol,timeframe,start,end = row
        if any(not isinstance(x,str) or not x for x in (venue,market,symbol,timeframe)):
            raise ValueError("invalid series identity")
        if any(type(x) is not int or x<0 for x in (start,end)) or end<=start:
            raise ValueError("invalid series time")
        identity = (venue,market,symbol,timeframe)
        if (identity,start) in seen:
            raise ValueError("duplicate candle identity")
        seen.add((identity,start))
        identities.add(identity)
    if len(identities)!=1:
        raise ValueError("mixed instrument or timeframe")
    return next(iter(identities))
