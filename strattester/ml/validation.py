from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WalkForwardSplit:
    train:tuple[int,...]
    test:tuple[int,...]

def walk_forward_splits(n, *, train_size, test_size, purge=0, step=None):
    n=int(n); train_size=int(train_size); test_size=int(test_size); purge=max(0,int(purge))
    step=int(step or test_size)
    out=[]; start=0
    while True:
        train_end=start+train_size
        test_start=train_end+purge
        test_end=test_start+test_size
        if test_end>n:break
        out.append(WalkForwardSplit(tuple(range(start,train_end)),tuple(range(test_start,test_end))))
        start+=step
    return tuple(out)
