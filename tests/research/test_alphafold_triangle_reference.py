"""Independent explicit-index tests for triangle multiplication."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_triangle import build_triangle_updates


@pytest.mark.parametrize("incoming", [False, True])
def test_triangle_matches_explicit_index_contraction(incoming):
    torch.manual_seed(42)
    module = build_triangle_updates(3, 5)[int(incoming)].double()
    z = torch.randn(1, 3, 3, 3, dtype=torch.float64)
    norm = module.norm(z)
    a = module.left(norm) * torch.sigmoid(module.left_gate(norm))
    b = module.right(norm) * torch.sigmoid(module.right_gate(norm))
    expected = torch.zeros_like(a)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                if incoming:
                    expected[:, i, j] += a[:, k, j] * b[:, k, i]
                else:
                    expected[:, i, j] += a[:, i, k] * b[:, j, k]
    expected = module.output(module.center_norm(expected)) * torch.sigmoid(module.output_gate(norm))
    torch.testing.assert_close(module(z), expected, atol=1e-10, rtol=1e-10)


def test_budget_fails_closed():
    module = build_triangle_updates(4, 8, max_pair_elements=30)[0]
    with pytest.raises(ValueError, match="budget"):
        module(torch.zeros(1, 3, 3, 4))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.5, -1.0])
def test_mask_rejects_invalid_values(bad):
    module = build_triangle_updates(4, 8)[0]
    mask = torch.ones(1, 3, 3)
    mask[0, 0, 0] = bad
    with pytest.raises(ValueError, match="mask"):
        module(torch.zeros(1, 3, 3, 4), mask)
