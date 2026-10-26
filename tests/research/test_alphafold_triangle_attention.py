"""Adversarial tests for independent triangle attention adaptation."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_triangle_attention import build_triangle_attention


@pytest.mark.parametrize("ending", [False, True])
def test_attention_gradients_and_mask(ending):
    module = build_triangle_attention(8, 2)[int(ending)]
    pair = torch.randn(1, 4, 4, 8, requires_grad=True)
    mask = torch.ones(1, 4, 4)
    mask[:, 3, :] = 0
    result = module(pair, mask)
    assert result.shape == pair.shape
    assert torch.isfinite(result).all()
    assert torch.count_nonzero(result[:, 3, :]) == 0
    result.square().sum().backward()
    assert pair.grad is not None and torch.isfinite(pair.grad).all()


@pytest.mark.parametrize("ending", [False, True])
def test_all_masked_rows_are_zero_and_finite(ending):
    module = build_triangle_attention(8, 2)[int(ending)]
    result = module(torch.randn(1, 3, 3, 8), torch.zeros(1, 3, 3))
    assert torch.count_nonzero(result) == 0
    assert torch.isfinite(result).all()


def test_attention_budget_rejected():
    module = build_triangle_attention(8, 2, max_attention_elements=10)[0]
    with pytest.raises(ValueError, match="budget"):
        module(torch.zeros(1, 3, 3, 8))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0.5])
def test_bad_mask_rejected(value):
    module = build_triangle_attention(8, 2)[0]
    mask = torch.ones(1, 3, 3)
    mask[0, 0, 0] = value
    with pytest.raises(ValueError):
        module(torch.zeros(1, 3, 3, 8), mask)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_cpu_forward():
    torch.manual_seed(11)
    cpu = build_triangle_attention(8, 2)[0].eval()
    gpu = build_triangle_attention(8, 2)[0].eval().cuda()
    gpu.load_state_dict(cpu.state_dict())
    pair = torch.randn(1, 3, 3, 8)
    torch.testing.assert_close(cpu(pair), gpu(pair.cuda()).cpu(), atol=1e-5, rtol=1e-4)
