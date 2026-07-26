"""Stage 2 — batched scan vs token-by-token / chunked streaming equivalence.

Tolerance contract: float32 max abs error ≤ 1e-5. bfloat16 uses a documented,
looser tolerance because the *inputs/projections* run in reduced precision even
though the scan itself accumulates in float32.
"""

import pytest
import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig
from symbolu.lightweight_phase.streaming import run_chunked, stream_tokens, max_abs_error

FP32_TOL = 1e-5
BF16_TOL = 3e-2  # documented reduced-precision tolerance


def _mk(seed=0, **kw):
    torch.manual_seed(seed)
    return LightweightPhaseAttention(PhaseConfig(**kw)).eval()


@pytest.mark.parametrize("N", [1, 2, 5, 16])
@pytest.mark.parametrize("B", [1, 3])
@pytest.mark.parametrize("H", [1, 4])
def test_token_by_token_equivalence(N, B, H):
    layer = _mk(embed_dim=32, num_heads=H)
    x = torch.randn(B, N, 32)
    y = layer(x)
    y_stream = stream_tokens(layer, x)
    assert max_abs_error(y, y_stream) <= FP32_TOL


@pytest.mark.parametrize("chunks", [[3, 3], [1, 2, 3], [4, 1, 1], [6], [2, 2, 2]])
def test_chunked_equivalence(chunks):
    N = sum(chunks)
    layer = _mk(embed_dim=32, num_heads=4)
    x = torch.randn(2, N, 32)
    y = layer(x)
    y_chunked = run_chunked(layer, x, chunks)
    assert max_abs_error(y, y_chunked) <= FP32_TOL


@pytest.mark.parametrize("decay", [
    dict(decay_mode="fixed_scalar", gamma_min=0.5, gamma_max=1.0, initial_gamma=0.9),
    dict(decay_mode="fixed_per_head", gamma_min=0.9, gamma_max=0.999),
    dict(decay_mode="learned_per_head", gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95),
])
def test_streaming_equivalence_with_decay(decay):
    layer = _mk(embed_dim=32, num_heads=4, **decay)
    x = torch.randn(2, 12, 32)
    y = layer(x)
    y_stream = stream_tokens(layer, x)
    y_chunked = run_chunked(layer, x, [5, 4, 3])
    assert max_abs_error(y, y_stream) <= FP32_TOL
    assert max_abs_error(y, y_chunked) <= FP32_TOL


def test_random_initial_state_and_continuation():
    """A random initial state used two ways (whole vs split) must agree."""
    layer = _mk(embed_dim=32, num_heads=4)
    x = torch.randn(2, 10, 32)
    # Build a legitimate initial state by running a warmup chunk.
    warm = layer(torch.randn(2, 4, 32), return_state=True)
    st0 = warm.state
    y_whole = layer(x, initial_state=st0)
    y_split = run_chunked(layer, x, [4, 6], initial_state=st0)
    assert max_abs_error(y_whole, y_split) <= FP32_TOL


def test_state_reset_gives_independent_stream():
    layer = _mk(embed_dim=16, num_heads=2)
    x = torch.randn(1, 5, 16)
    y_fresh = layer(x)
    # streaming from None (reset) must equal batched-from-scratch
    y_reset = stream_tokens(layer, x, initial_state=None)
    assert max_abs_error(y_fresh, y_reset) <= FP32_TOL


def test_state_memory_constant_across_context_length():
    """INV-STATE-O: carried state numel does not grow with N."""
    layer = _mk(embed_dim=32, num_heads=4)
    sizes = {}
    for N in (2, 8, 64, 256):
        out = layer(torch.randn(1, N, 32), return_state=True)
        sizes[N] = out.state.numel()
    assert len(set(sizes.values())) == 1, sizes


@pytest.mark.skipif(not hasattr(torch, "bfloat16"), reason="bf16 unavailable")
def test_bfloat16_streaming_equivalence():
    layer = _mk(embed_dim=32, num_heads=4)
    x = torch.randn(2, 8, 32).to(torch.bfloat16)
    layer_bf = layer.to(torch.bfloat16)
    y = layer_bf(x)
    y_stream = stream_tokens(layer_bf, x)
    assert y.dtype == torch.bfloat16
    err = (y.float() - y_stream.float()).abs().max().item()
    assert err <= BF16_TOL, err
