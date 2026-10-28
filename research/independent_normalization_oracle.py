"""Independent train-only normalization oracle."""
import math

def train_only_zscore(train, evaluation):
    train = tuple(train)
    evaluation = tuple(evaluation)
    if not train or any(type(x) not in (float,int) or not math.isfinite(x) for x in train + evaluation):
        raise ValueError("invalid normalization values")
    mu = math.fsum(train) / len(train)
    variance = math.fsum((x - mu)**2 for x in train) / len(train)
    scale = math.sqrt(variance)
    if not scale and any(x != mu for x in evaluation):
        raise ValueError("unseen value with constant train feature")
    return tuple((x - mu)/scale if scale else 0. for x in evaluation), (mu,scale)
