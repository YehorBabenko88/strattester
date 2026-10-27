"""MSA attention causal and masking regression tests."""
import pytest

torch = pytest.importorskip("torch")
from strattester.research.alphafold_msa_attention import build_msa_row_attention


def test_row_attention_shape_and_gradients():
    torch.manual_seed(41)
    model = build_msa_row_attention(8, 6, heads=2)
    msa = torch.randn(1, 2, 4, 8, requires_grad=True)
    pair = torch.randn(1, 4, 4, 6, requires_grad=True)
    out = model(msa, pair, causal=True)
    assert out.shape == msa.shape
    out.square().mean().backward()
    assert msa.grad is not None and torch.isfinite(msa.grad).all()
    assert pair.grad is not None and torch.isfinite(pair.grad).all()


def test_causal_attention_does_not_read_future_tokens():
    torch.manual_seed(42)
    model = build_msa_row_attention(8, 6, heads=2).eval()
    msa = torch.randn(1, 2, 4, 8)
    pair = torch.randn(1, 4, 4, 6)
    changed = msa.clone()
    changed[:, :, 3, :] += 1000
    with torch.no_grad():
        original = model(msa, pair, causal=True)
        perturbed = model(changed, pair, causal=True)
    torch.testing.assert_close(original[:, :, :3], perturbed[:, :, :3])


def test_attention_masks_and_budget():
    model = build_msa_row_attention(8, 6, heads=2, max_attention_elements=40)
    msa = torch.randn(1, 2, 4, 8)
    pair = torch.randn(1, 4, 4, 6)
    with pytest.raises(ValueError, match="budget"):
        model(msa, pair)
    model = build_msa_row_attention(8, 6, heads=2)
    out = model(msa, pair, torch.zeros(1, 2, 4), causal=True)
    assert torch.count_nonzero(out) == 0
