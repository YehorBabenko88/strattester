import pytest
from strattester.research.financial_evoformer import build_financial_model


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
