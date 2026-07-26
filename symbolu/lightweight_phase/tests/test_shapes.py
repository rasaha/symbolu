"""Stage 1 — input/output shapes, multi-head layout, state layout."""

import pytest
import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig, PhaseState


@pytest.mark.parametrize("B,N,D,H", [(1, 1, 8, 2), (2, 5, 32, 4), (3, 16, 48, 6), (2, 1, 64, 8)])
def test_output_shape(B, N, D, H):
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=D, num_heads=H))
    x = torch.randn(B, N, D)
    y = layer(x)
    assert y.shape == (B, N, D)


def test_state_layout_is_multihead():
    cfg = PhaseConfig(embed_dim=48, num_heads=6)
    layer = LightweightPhaseAttention(cfg)
    x = torch.randn(2, 5, 48)
    out = layer(x, return_state=True)
    st = out.state
    assert isinstance(st, PhaseState)
    assert st.complex_memory.shape == (2, 6, 8)  # [B, H, Dh]
    assert st.amplitude_sum.shape == (2, 6, 8)
    assert st.complex_memory.is_complex()
    assert st.position == 5


def test_diagnostics_present_when_requested():
    cfg = PhaseConfig(embed_dim=32, num_heads=4)
    layer = LightweightPhaseAttention(cfg)
    out = layer(torch.randn(2, 6, 32), return_diagnostics=True)
    assert out.diagnostics is not None
    assert out.diagnostics["R_k"].shape == (4,)
    assert out.diagnostics["R_q"].shape == (4,)


def test_embed_dim_divisibility_enforced():
    with pytest.raises(ValueError):
        PhaseConfig(embed_dim=30, num_heads=4)


def test_step_shapes():
    cfg = PhaseConfig(embed_dim=16, num_heads=2)
    layer = LightweightPhaseAttention(cfg)
    o, st = layer.step(torch.randn(3, 16), None)
    assert o.shape == (3, 16)
    assert st.position == 1
    o2, st2 = layer.step(torch.randn(3, 16), st)
    assert st2.position == 2
