"""Stage 1/3 — numerical stability: finite outputs on hard inputs, bounded state."""

import pytest
import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig
from symbolu.lightweight_phase.streaming import stream_tokens, max_abs_error


@pytest.mark.parametrize("scale", [1e-4, 1.0, 1e2, 1e4])
def test_finite_output_across_input_scales(scale):
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4)).eval()
    x = torch.randn(2, 32, 32) * scale
    y = layer(x)
    assert torch.isfinite(y).all(), f"non-finite at scale {scale}"


def test_long_sequence_state_bounded_under_decay():
    """With decay < 1 the state magnitude stays bounded on a long sequence."""
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(
        PhaseConfig(embed_dim=32, num_heads=4, decay_mode="fixed_scalar",
                    gamma_min=0.5, gamma_max=1.0, initial_gamma=0.9)
    ).eval()
    x = torch.randn(1, 512, 32)
    out = layer(x, return_state=True, return_diagnostics=True)
    assert torch.isfinite(out.output).all()
    assert torch.isfinite(out.state.complex_memory).all()
    # bounded: |S| should not blow up like a non-decaying random walk of 512 steps
    assert out.state.complex_memory.abs().max().item() < 1e3


def test_lower_decay_forgets_faster():
    """A distant impulse influences the final output less as gamma decreases."""
    torch.manual_seed(0)
    D = 32
    base = LightweightPhaseAttention(
        PhaseConfig(embed_dim=D, num_heads=4, decay_mode="fixed_scalar",
                    gamma_min=0.5, gamma_max=1.0, initial_gamma=0.99)
    ).eval()

    # Random filler + a distinct "fact" token far in the past. (A constant
    # impulse vector is invalid here: LayerNorm maps any constant token to a
    # fixed value, erasing the perturbation.)
    torch.manual_seed(7)
    filler = torch.randn(1, 60, D)
    fact = torch.randn(1, D)

    def final_sensitivity(layer):
        x = filler.clone()
        x[:, 0] = fact
        y1 = layer(x)[:, -1]
        x2 = filler.clone()  # same filler, fact removed
        y2 = layer(x2)[:, -1]
        return (y1 - y2).abs().mean().item()

    s_high = final_sensitivity(base)

    torch.manual_seed(0)
    low = LightweightPhaseAttention(
        PhaseConfig(embed_dim=D, num_heads=4, decay_mode="fixed_scalar",
                    gamma_min=0.5, gamma_max=1.0, initial_gamma=0.7)
    ).eval()
    low.load_state_dict(base.state_dict())
    s_low = final_sensitivity(low)

    assert s_low < s_high, f"expected lower gamma to forget faster: {s_low} !< {s_high}"


def test_learned_decay_stays_in_range():
    cfg = PhaseConfig(embed_dim=32, num_heads=8, decay_mode="learned_per_head",
                      gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95)
    layer = LightweightPhaseAttention(cfg)
    # push parameters around, gamma must remain in [gamma_min, gamma_max]
    with torch.no_grad():
        layer.decay_theta.copy_(torch.tensor([-1e3, 1e3, 0.0, 5.0, -5.0, 2.0, -2.0, 0.5]))
    g = layer.gamma_per_head("cpu")
    assert (g >= cfg.gamma_min - 1e-6).all() and (g <= cfg.gamma_max + 1e-6).all(), g
