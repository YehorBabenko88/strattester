"""Metamorphic oracle for triangle attention orientation.

Ending attention on z must equal starting attention on z^T, transposed back,
when parameters are identical. This catches incorrect pair-bias orientation.
"""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_triangle_attention import build_triangle_attention


def test_ending_is_transposed_starting_with_same_weights():
    torch.manual_seed(137)
    starting, ending = build_triangle_attention(8, 2)
    ending.load_state_dict(starting.state_dict())
    z = torch.randn(2, 4, 4, 8)
    mask = torch.ones(2, 4, 4)
    mask[:, 0, 2] = 0
    actual = ending(z, mask)
    reference = starting(z.transpose(1, 2), mask.transpose(1, 2)).transpose(1, 2)
    torch.testing.assert_close(actual, reference, atol=1e-6, rtol=1e-6)


def test_ending_transposition_gradient_oracle():
    torch.manual_seed(138)
    starting, ending = build_triangle_attention(8, 2)
    ending.load_state_dict(starting.state_dict())
    z = torch.randn(1, 3, 3, 8, requires_grad=True)
    a = ending(z).square().sum()
    b = starting(z.transpose(1, 2)).transpose(1, 2).square().sum()
    grad_a = torch.autograd.grad(a, z, retain_graph=True)[0]
    grad_b = torch.autograd.grad(b, z)[0]
    torch.testing.assert_close(grad_a, grad_b, atol=1e-5, rtol=1e-5)
