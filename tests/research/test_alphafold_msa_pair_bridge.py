"""End-to-end offline MSA/pair bridge contracts."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_msa_pair_bridge import build_msa_pair_bridge


def test_bridge_shapes_mask_and_gradients():
    torch.manual_seed(11)
    model = build_msa_pair_bridge(4, 8, 3, heads=2, max_tokens=4)
    msa = torch.randn(1, 2, 3, 4, requires_grad=True)
    mask = torch.tensor([[[1, 1, 0], [1, 0, 0]]])
    out = model(msa, msa_mask=mask)
    assert out.shape == (1, 3, 3, 8)
    assert torch.count_nonzero(out[:, 2]) == 0
    assert torch.count_nonzero(out[:, :, 2]) == 0
    out.square().mean().backward()
    assert msa.grad is not None and torch.isfinite(msa.grad).all()


def test_bridge_zero_mask_and_pair_rejection():
    model = build_msa_pair_bridge(4, 8, 3, heads=2, max_tokens=4)
    msa = torch.randn(1, 2, 3, 4)
    out = model(msa, msa_mask=torch.zeros(1, 2, 3))
    assert torch.count_nonzero(out) == 0
    with pytest.raises(ValueError, match="initial pair"):
        model(msa, pair=torch.zeros(1, 3, 3, 7))


def test_bridge_rejects_bad_msa_mask():
    model = build_msa_pair_bridge(4, 8, 3, heads=2, max_tokens=4)
    with pytest.raises(ValueError, match="MSA mask"):
        model(torch.zeros(1, 2, 3, 4), msa_mask=torch.ones(1, 2, 3) * 0.5)
