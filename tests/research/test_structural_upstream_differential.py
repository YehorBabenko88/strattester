"""Independent NumPy equations from AlphaFold c77e5d2 modules.py/config.py.

No torch normalization, projection, softmax or operator implements expectations.
Parameter arrays are mapped explicitly; these are small CPU equation tests,
not execution of JAX/Haiku, upstream weights, or a whole-network equivalence.
"""
from dataclasses import asdict
from hashlib import sha256
import json

import numpy as np
import pytest
import torch

from strattester.research.alphafold_msa_attention import build_msa_row_attention
from strattester.research.alphafold_triangle import build_triangle_updates
from strattester.research.alphafold_triangle_attention import build_triangle_attention
from strattester.research.financial_checkpoint import load_checkpoint
from strattester.research.financial_structural_model import (
    StructuralConfig, build_column_attention, build_structural_model,
)


def arrays(module):
    return {k: v.detach().numpy().copy() for k, v in module.state_dict().items()}


def affine(x, p, name):
    y = np.matmul(x, p[name + '.weight'].T)
    return y + p.get(name + '.bias', 0)


def norm(x, p, name):
    mean = np.mean(x, axis=-1, keepdims=True)
    variance = np.mean((x - mean) ** 2, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance + 1e-5) * p[name + '.weight'] + p[name + '.bias']


def sigmoid(x):
    return .5 * (1 + np.tanh(x / 2))


def attention_reference(kind, x, mask, p, pair=None):
    """Scalar query/key/head loops; upstream Attention plus query-mask policy.

    Column grouping follows MSAColumnAttention; triangle ending coordinates
    follow per_column swap in TriangleAttention. Bias is indexed by query/key
    vertices, independent of the fixed vertex, per upstream nonbatched_bias.
    """
    b, groups, length, channels = x.shape
    heads, d = 2, channels // 2
    triangle = kind.startswith('triangle')
    if kind == 'column':
        x, mask = np.swapaxes(x, 1, 2), np.swapaxes(mask, 1, 2)
    elif kind == 'triangle_end':
        x, mask = np.swapaxes(x, 1, 2), np.swapaxes(mask, 1, 2)
    b, groups, length, channels = x.shape
    z = norm(x, p, 'msa_norm' if kind == 'row' else 'norm')
    if triangle:
        q, k, v = [affine(z, p, name).reshape(b, groups, length, heads, d) for name in ('q', 'k', 'v')]
        bias = affine(z, p, 'bias')
    else:
        q, k, v = np.split(affine(z, p, 'qkv'), 3, axis=-1)
        q, k, v = [a.reshape(b, groups, length, heads, d) for a in (q, k, v)]
        bias = affine(norm(pair, p, 'pair_norm'), p, 'pair_bias') if kind == 'row' else None
    result = np.zeros_like(x)
    for batch in range(b):
        for group in range(groups):
            valid = np.flatnonzero(mask[batch, group])
            for query in range(length):
                if not mask[batch, group, query]:
                    continue
                attended = np.zeros(channels)
                for head in range(heads):
                    logits = np.array([
                        np.dot(q[batch, group, query, head], k[batch, group, key, head]) / np.sqrt(d)
                        + (bias[batch, query, key, head] if bias is not None else 0)
                        for key in valid
                    ])
                    weights = np.exp(logits - max(logits))
                    weights /= weights.sum()
                    for offset in range(d):
                        attended[head * d + offset] = sum(
                            w * v[batch, group, key, head, offset] for w, key in zip(weights, valid)
                        )
                result[batch, group, query] = affine(
                    attended * sigmoid(affine(z[batch, group, query], p, 'gate')), p, 'output'
                )
    return np.swapaxes(result, 1, 2) if kind in ('column', 'triangle_end') else result


def fixture(kind):
    torch.manual_seed(733)
    if kind == 'row':
        module = build_msa_row_attention(4, 4, 2)
    elif kind == 'column':
        module = build_column_attention(4, 2)
    else:
        module = build_triangle_attention(4, 2)[kind == 'triangle_end']
    rng = np.random.default_rng(29)
    x = rng.normal(size=(1, 3, 3, 4))
    pair = rng.normal(size=(1, 3, 3, 4))
    mask = np.array([[[1, 0, 1], [1, 1, 0], [0, 0, 0]]], dtype=bool)
    return module.double(), x, mask, pair


def invoke(module, kind, x, mask, pair):
    return module(x, pair, mask) if kind == 'row' else module(x, mask)


@pytest.mark.parametrize('kind', ['row', 'column', 'triangle_start', 'triangle_end'])
@pytest.mark.parametrize('case', ['dense', 'asymmetric_empty', 'extreme_finite'])
def test_attention_matches_independent_upstream_equations(kind, case):
    # Catches head/key axes, pair-bias vertex and ending-orientation errors.
    module, x, mask, pair = fixture(kind)
    if case == 'dense':
        mask[:] = True
    if case == 'extreme_finite':
        x *= 1e6
        pair *= 1e6
    expected = attention_reference(kind, x, mask, arrays(module), pair)
    actual = invoke(module, kind, torch.tensor(x), torch.tensor(mask), torch.tensor(pair))
    np.testing.assert_allclose(actual.detach().numpy(), expected, rtol=2e-9, atol=2e-9)


@pytest.mark.parametrize('kind', ['row', 'column', 'triangle_start', 'triangle_end'])
def test_attention_input_and_weight_gradients_match_numpy_finite_differences(kind):
    # Catches incorrect backward paths even if outputs happen to match.
    module, x, mask, pair = fixture(kind)
    p = arrays(module)
    tx = torch.tensor(x, requires_grad=True)
    coefficients = np.random.default_rng(20).normal(size=x.shape)
    loss = (invoke(module, kind, tx, torch.tensor(mask), torch.tensor(pair)) * torch.tensor(coefficients)).sum()
    loss.backward()
    def objective():
        return np.sum(attention_reference(kind, x, mask, p, pair) * coefficients)
    step = 1e-6
    key = 'q.weight' if kind.startswith('triangle') else 'qkv.weight'
    for target, index, gradient in (
        (x, (0, 0, 0, 1), tx.grad[0, 0, 0, 1].item()),
        (p[key], (0, 1), dict(module.named_parameters())[key].grad[0, 1].item()),
    ):
        original = target[index]
        target[index] = original + step
        plus = objective()
        target[index] = original - step
        minus = objective()
        target[index] = original
        assert gradient == pytest.approx((plus - minus) / (2 * step), rel=2e-5, abs=2e-7)


def multiplication_reference(x, mask, p, incoming):
    z = norm(x, p, 'norm')
    left = affine(z, p, 'left') * sigmoid(affine(z, p, 'left_gate')) * mask[..., None]
    right = affine(z, p, 'right') * sigmoid(affine(z, p, 'right_gate')) * mask[..., None]
    mixed = np.zeros_like(left)
    for i in range(x.shape[1]):
        for j in range(x.shape[2]):
            for k in range(x.shape[1]):
                # Pinned config.py: kjc,kic->ijc, NOT kic,kjc->ijc.
                mixed[:, i, j] += left[:, k, j] * right[:, k, i] if incoming else left[:, i, k] * right[:, j, k]
    return affine(norm(mixed, p, 'center_norm'), p, 'output') * sigmoid(affine(z, p, 'output_gate')) * mask[..., None]


@pytest.mark.parametrize('incoming', [False, True])
def test_triangle_multiplication_uses_pinned_upstream_projection_orientation(incoming):
    torch.manual_seed(27)
    module = build_triangle_updates(4, 3)[incoming].double()
    rng = np.random.default_rng(3)
    x = rng.normal(size=(1, 3, 3, 4))
    mask = np.array([[[1, 0, 1], [1, 1, 0], [0, 1, 1]]], dtype=bool)
    expected = multiplication_reference(x, mask, arrays(module), incoming)
    np.testing.assert_allclose(module(torch.tensor(x), torch.tensor(mask)).detach().numpy(), expected, rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_column_rejects_nonfinite_input_before_normalization(bad):
    module = build_column_attention(4, 2)
    x = torch.zeros(1, 2, 2, 4)
    x[0, 0, 0, 0] = bad
    entered = []
    handle = module.norm.register_forward_pre_hook(lambda *args: entered.append(True))
    try:
        with pytest.raises(ValueError, match='nonfinite'):
            module(x, torch.ones(1, 2, 2))
    finally:
        handle.remove()
    assert not entered


@pytest.mark.parametrize('version', [None, 1, True])
def test_checkpoint_rejects_legacy_equations_before_model_allocation(tmp_path, monkeypatch, version):
    config = asdict(StructuralConfig())
    config.pop('model_equations_version', None)
    if version is not None:
        config['model_equations_version'] = version
    payload = dict(version=1, config=config, dataset_sha256='a' * 64, seed=0, tensors={})
    data = json.dumps(payload).encode()
    path = tmp_path / 'legacy.json'
    path.write_bytes(data)
    monkeypatch.setattr(torch.nn, 'Linear', lambda *a, **kw: pytest.fail('legacy checkpoint allocated a model'))
    with pytest.raises(ValueError):
        load_checkpoint(path, sha256(data).hexdigest())


@pytest.mark.parametrize('recycles', [0, 1, 2])
def test_recycling_state_and_distribution_head_have_independent_numpy_reference(recycles):
    # The layer outputs are observed states, not a whole-network oracle.
    # Detects base omission, wrong state normalization, stale or absent recycle,
    # target-last-token and pooled-pair/head indexing defects.
    torch.manual_seed(12)
    model = build_structural_model(StructuralConfig(recycles=recycles)).double()
    x = np.random.default_rng(3).normal(size=(1, 2, 3, 3))
    mask = np.array([[[1, 0, 1], [1, 1, 0]]], dtype=bool)
    entered, exited = [], []
    first = model.layers[0].register_forward_pre_hook(lambda m, args: entered.append(tuple(t.detach().numpy().copy() for t in args[:2])))
    last = model.layers[-1].register_forward_hook(lambda m, args, out: exited.append(tuple(t.detach().numpy().copy() for t in out)))
    try:
        actual = model(torch.tensor(x), torch.tensor(mask)).detach().numpy()
    finally:
        first.remove(); last.remove()
    p = arrays(model)
    base = affine(x * mask[..., None], p, 'input') * mask[..., None]
    valid = mask.any(axis=1)
    pm = valid[:, :, None] & valid[:, None, :]
    assert len(entered) == recycles + 1
    np.testing.assert_allclose(entered[0][0], base, atol=1e-12)
    np.testing.assert_array_equal(entered[0][1], np.zeros((1, 3, 3, 8)))
    for i in range(1, recycles + 1):
        np.testing.assert_allclose(entered[i][0], base + norm(exited[i-1][0], p, 'recycle_msa') * mask[..., None], rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(entered[i][1], norm(exited[i-1][1], p, 'recycle_pair') * pm[..., None], rtol=1e-10, atol=1e-10)
    msa, pair = exited[-1]
    single = affine(msa[0, 0, 2], p, 'single')
    pooled = pair[0, 2, valid[0]].mean(axis=0)
    raw = affine(np.concatenate((single, pooled)), p, 'head')
    expected = [[raw[0], np.clip(np.logaddexp(0, raw[1]), 1e-5, 10)]]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)


def test_recycled_prediction_has_zero_masked_input_gradient():
    torch.manual_seed(12)
    model = build_structural_model(StructuralConfig(recycles=2)).double()
    x = torch.randn(1, 2, 3, 3, dtype=torch.float64, requires_grad=True)
    mask = torch.tensor([[[1, 0, 1], [1, 1, 0]]], dtype=torch.bool)
    model(x, mask).sum().backward()
    assert torch.count_nonzero(x.grad[~mask]) == 0
    assert torch.isfinite(x.grad).all() and torch.count_nonzero(x.grad[mask]) > 0
