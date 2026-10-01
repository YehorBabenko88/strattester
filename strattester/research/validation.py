from __future__ import annotations
from dataclasses import dataclass
from typing import Generic,TypeVar,Mapping,Any
T=TypeVar('T')

@dataclass(frozen=True)
class ChronologicalSplit(Generic[T]):
    train:tuple[T,...]
    validation:tuple[T,...]
    test:tuple[T,...]

@dataclass(frozen=True)
class FrozenParameters:
    values:Mapping[str,Any]
    selected_through:int

def chronological_split(rows,*,train_size:int,validation_size:int,test_size:int)->ChronologicalSplit:
    xs=tuple(rows)
    total=train_size+validation_size+test_size
    if total>len(xs): raise ValueError('split exceeds available rows')
    return ChronologicalSplit(xs[:train_size],xs[train_size:train_size+validation_size],xs[train_size+validation_size:total])

def walk_forward_folds(rows,*,train_size:int,validation_size:int,test_size:int,step:int):
    if min(train_size,validation_size,test_size,step)<=0: raise ValueError('sizes must be positive')
    xs=tuple(rows); out=[]
    width=train_size+validation_size+test_size
    start=0
    while start+width<=len(xs):
        chunk=xs[start:start+width]
        out.append(chronological_split(chunk,train_size=train_size,validation_size=validation_size,test_size=test_size))
        start+=step
    return tuple(out)

def freeze_parameters(values,*,selected_through:int)->FrozenParameters:
    return FrozenParameters(dict(values),selected_through)
