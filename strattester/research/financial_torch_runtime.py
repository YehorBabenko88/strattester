"""Cooperative CPU research state coordination, never OS/GPU isolation.

All participating model constructors, fits and checkpoint reconstructions share
one reentrant slot. Arbitrary external Torch users must coordinate separately
or use another process. No CUDA state/device is read, seeded or qualified here.
"""
from contextlib import contextmanager
from functools import wraps
import threading
import time
from .financial_contract import integer

_SLOT=threading.RLock()
_MAX_WAIT_SECONDS=30.


def _check_cancel(cancel):
    if cancel():
        from .financial_training import TrainingCancelled
        raise TrainingCancelled('cancelled waiting for CPU research slot')


@contextmanager
def cpu_research_slot(cancel=lambda:False):
    deadline=time.monotonic()+_MAX_WAIT_SECONDS
    _check_cancel(cancel)
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('CPU research slot admission timeout')
        if _SLOT.acquire(timeout=min(.05,remaining)):break
        _check_cancel(cancel)
    try:
        _check_cancel(cancel)
        yield
    finally:
        _SLOT.release()


def serialize_cpu_research(function):
    @wraps(function)
    def run(*args,**kwargs):
        with cpu_research_slot(kwargs.get('cancel',lambda:False)):
            return function(*args,**kwargs)
    return run


@contextmanager
def cpu_research_state(*,seed=None,deterministic=None):
    if seed is not None:
        integer(seed,'CPU seed')
        if seed>2**64-1:raise ValueError('CPU seed range')
    if deterministic is not None and type(deterministic) is not bool:
        raise ValueError('deterministic CPU policy')
    with cpu_research_slot():
        import torch
        previous=torch.random.get_rng_state()
        enabled=torch.are_deterministic_algorithms_enabled()
        warn_only=torch.is_deterministic_algorithms_warn_only_enabled()
        try:
            if seed is not None:torch.random.default_generator.manual_seed(seed)
            if deterministic is not None:torch.use_deterministic_algorithms(deterministic,warn_only=False)
            yield
        finally:
            torch.random.set_rng_state(previous)
            torch.use_deterministic_algorithms(enabled,warn_only=warn_only)
