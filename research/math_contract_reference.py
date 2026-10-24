"""Reference mathematical invariants; offline, standard-library only."""
import math


def log_returns(prices):
    if any(not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError("prices must be finite and positive")
    return [math.log(b / a) for a, b in zip(prices, prices[1:])]


def sample_volatility(returns):
    if len(returns) < 2 or any(not math.isfinite(x) for x in returns):
        raise ValueError("need at least two finite returns")
    mu = math.fsum(returns) / len(returns)
    return math.sqrt(math.fsum((x - mu) ** 2 for x in returns) / (len(returns) - 1))


def validate_observations(rows, cutoff_ns, watermark_ns):
    """Fail closed: no open candle, duplicate ID, future dependency or gap."""
    if (type(cutoff_ns) is not int or type(watermark_ns) is not int
            or cutoff_ns < 0 or watermark_ns < 0 or watermark_ns > cutoff_ns):
        raise ValueError("invalid cutoff or watermark")
    seen = set()
    for row in rows:
        keys = ("event_id", "event_time_ns", "available_time_ns", "bucket_end_ns",
                "eligible", "quality_status", "gap_status")
        if any(k not in row for k in keys):
            raise ValueError("missing provenance field")
        if (not isinstance(row["event_id"], str) or not row["event_id"]
                or any(type(row[k]) is not int or row[k] < 0 for k in
                       ("event_time_ns", "available_time_ns", "bucket_end_ns"))
                or type(row["eligible"]) is not bool
                or row["event_time_ns"] > row["available_time_ns"]
                or row["available_time_ns"] < row["bucket_end_ns"]):
            raise ValueError("invalid observation types or timestamp ordering")
        if row["event_id"] in seen:
            raise ValueError("duplicate event")
        seen.add(row["event_id"])
        if (not row["eligible"] or row["quality_status"] != "VERIFIED"
                or row["gap_status"] != "NONE"
                or row["available_time_ns"] > cutoff_ns
                or row["bucket_end_ns"] > watermark_ns
                or row["event_time_ns"] >= row["bucket_end_ns"]):
            raise ValueError("ineligible or noncausal observation")
    return True


def pair_dependency_mask(latest_available_ns, cutoffs_ns, max_cells=1_000_000):
    """Per-query dependency mask, for all pair/triangle edges."""
    n = len(latest_available_ns)
    if (n != len(cutoffs_ns) or n * n > max_cells or
            any(type(x) is not int or x < 0 for x in
                list(latest_available_ns) + list(cutoffs_ns))):
        raise ValueError("invalid pair shape, budget or timestamps")
    return [[a <= cutoff and b <= cutoff for b in latest_available_ns]
            for a, cutoff in zip(latest_available_ns, cutoffs_ns)]


def triangle_path_valid(mask, i, j, k):
    return mask[i][j] and mask[i][k] and mask[k][j]
