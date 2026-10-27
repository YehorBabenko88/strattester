"""Pure interval-oracle for purged/embargoed train/evaluation labels."""
def validate_disjoint_labels(train, evaluation, embargo_ns=0):
    if type(embargo_ns) is not int or embargo_ns < 0:
        raise ValueError("invalid embargo")
    def check(group):
        out = []
        for interval in group:
            if (not isinstance(interval, (tuple, list)) or len(interval) != 2
                or any(type(v) is not int or v < 0 for v in interval)
                or interval[1] < interval[0]):
                raise ValueError("invalid label interval")
            out.append(tuple(interval))
        return out
    train, evaluation = check(train), check(evaluation)
    for a, b in train:
        for c, d in evaluation:
            if a <= d + embargo_ns and c <= b + embargo_ns:
                raise ValueError("label leakage or embargo violation")
    return True
