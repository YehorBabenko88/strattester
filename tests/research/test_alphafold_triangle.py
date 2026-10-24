"""CPU-first structural operator tests; optional GPU parity smoke test."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_triangle import build_triangle_updates


@pytest.mark.parametrize("incoming", [False, True])
def test_triangle_shapes_gradients_and_mask(incoming):
    module = build_triangle_updates(8, 12)[int(incoming)]
    pair = torch.randn(2, 4, 4, 8, requires_grad=True)
    mask = torch.ones(2, 4, 4)
    mask[:, -1, :] = 0
    result = module(pair, mask)
    assert result.shape == pair.shape
    assert torch.isfinite(result).all()
    assert torch.count_nonzero(result[:, -1]) == 0
    result.square().mean().backward()
    assert pair.grad is not None and torch.isfinite(pair.grad).all()


def test_deterministic_initialization_cpu():
    torch.manual_seed(77)
    a = build_triangle_updates(4, 8)[0]
    torch.manual_seed(77)
    b = build_triangle_updates(4, 8)[0]
    x = torch.randn(1, 3, 3, 4)
    torch.testing.assert_close(a(x), b(x), rtol=0, atol=0)


def test_reject_bad_shape_and_nonfinite():
    module = build_triangle_updates(4, 8)[0]
    with pytest.raises(ValueError):
        module(torch.zeros(1, 3, 2, 4))
    x = torch.zeros(1, 3, 3, 4)
    x[0, 0, 0, 0] = float("nan")
    with pytest.raises(ValueError):
        module(x)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_gpu_cpu_forward_parity():
    torch.manual_seed(9)
    cpu = build_triangle_updates(4, 8)[0].eval()
    gpu = build_triangle_updates(4, 8)[0].eval().cuda()
    gpu.load_state_dict(cpu.state_dict())
    x = torch.randn(1, 3, 3, 4)
    torch.testing.assert_close(cpu(x), gpu(x.cuda()).cpu(), rtol=1e-4, atol=1e-5)
