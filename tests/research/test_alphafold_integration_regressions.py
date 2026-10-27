"""Regressions for the independently reported integration defects."""
import pytest
import torch
from strattester.research.alphafold_adapter import encode_market
from strattester.research.alphafold_outer_product import build_outer_product_mean


@pytest.mark.parametrize('bad', [[.9,1.9,2.9,3.9],['0','1','2','3'],[False,1,2,3]])
def test_adapter_rejects_silent_timestamp_conversion(bad):
    with pytest.raises(ValueError, match='integer'):
        encode_market('BTCUSDT','1m',bad,[1,2,3,4],window=2)


def test_outer_track_admission_precedes_normalization():
    module = build_outer_product_mean(4, 4, 2, max_elements=100)
    entered = []
    handle = module.norm.register_forward_pre_hook(lambda *args: entered.append(True))
    with pytest.raises(ValueError, match='budget'):
        module(torch.zeros(1,100,2,4))
    handle.remove()
    assert not entered


@pytest.mark.parametrize('shape', [(0,1,2,4),(1,0,2,4)])
def test_outer_rejects_empty_axes(shape):
    with pytest.raises(ValueError):
        build_outer_product_mean(4,4,2)(torch.zeros(shape))


def test_outer_parameter_budget_before_constructor_allocation(monkeypatch):
    def reject_allocation(*args, **kwargs):
        raise AssertionError('parameter allocation reached before admission')
    monkeypatch.setattr(torch.nn, 'Linear', reject_allocation)
    with pytest.raises(ValueError, match='budget'):
        build_outer_product_mean(4, 100_000, 100_000, max_elements=100)
