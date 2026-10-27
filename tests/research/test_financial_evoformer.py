import pytest
from strattester.research.financial_evoformer import build_financial_model
from strattester.research.alphafold_security import PairBudget


def test_invalid_configuration():
    with pytest.raises(ValueError):
        build_financial_model(hidden=7, heads=4)


def test_optional_model_forward_and_gradients():
    torch = pytest.importorskip("torch")
    torch.manual_seed(11)
    model = build_financial_model(hidden=8, heads=2)
    single = torch.randn(2, 6, 3)
    pair = torch.cdist(single, single)
    output = model(single, pair)
    assert output.shape == (2, 2)
    output.square().mean().backward()
    assert any(p.grad is not None for p in model.parameters())
    with pytest.raises(ValueError):
        model(single, pair[:, :-1])


def test_reject_pair_memory_before_allocation():
    torch = pytest.importorskip('torch')
    model = build_financial_model(hidden=8, heads=2, budget=PairBudget(max_pair_bytes=1024))
    single = torch.zeros(2, 6, 3)
    pair = torch.zeros(2, 6, 6)
    with pytest.raises(ValueError, match='memory'):
        model(single, pair)


def test_reject_nonfinite_and_mismatched_dtype():
    torch = pytest.importorskip('torch')
    model = build_financial_model(hidden=8, heads=2)
    single = torch.zeros(1, 4, 3)
    pair = torch.zeros(1, 4, 4)
    pair[0, 0, 0] = float('nan')
    with pytest.raises(ValueError, match='nonfinite'):
        model(single, pair)
    with pytest.raises(ValueError, match='dtype'):
        model(single, torch.zeros(1, 4, 4, dtype=torch.float64))
