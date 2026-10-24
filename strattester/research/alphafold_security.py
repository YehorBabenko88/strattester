"""Fail-closed resource admission for experimental financial pair models."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class PairBudget:
    max_tokens: int = 256
    max_batch: int = 8
    max_pair_bytes: int = 256 * 1024 * 1024
    activation_multiplier: int = 12

def admit_pair_shape(batch: int, tokens: int, channels: int, *, element_bytes: int = 4, budget: PairBudget = PairBudget()) -> int:
    values = (batch, tokens, channels, element_bytes, budget.activation_multiplier)
    if any(type(v) is not int or v <= 0 for v in values):
        raise ValueError("positive integer dimensions required")
    if batch > budget.max_batch or tokens > budget.max_tokens:
        raise ValueError("pair dimensions exceed resource policy")
    estimate = batch * tokens * tokens * channels * element_bytes * budget.activation_multiplier
    if estimate > budget.max_pair_bytes:
        raise ValueError("estimated pair activation memory exceeds resource policy")
    return estimate
