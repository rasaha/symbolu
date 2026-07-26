"""Stage 1 — causal behavior: output at t depends only on tokens ≤ t."""

import pytest
import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig


@pytest.mark.parametrize("decay", [
    {},
    dict(decay_mode="fixed_scalar", gamma_min=0.5, gamma_max=1.0, initial_gamma=0.95),
    dict(decay_mode="fixed_per_head", gamma_min=0.9, gamma_max=0.999),
    dict(decay_mode="learned_per_head", gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95),
])
def test_future_tokens_do_not_affect_past_outputs(decay):
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4, **decay)).eval()
    x = torch.randn(2, 10, 32)
    y = layer(x)

    split = 6
    x_perturbed = x.clone()
    x_perturbed[:, split:] = torch.randn(2, 10 - split, 32)
    y_perturbed = layer(x_perturbed)

    # Positions before the perturbation must be identical.
    diff = (y[:, :split] - y_perturbed[:, :split]).abs().max().item()
    assert diff < 1e-6, f"causality violated: {diff}"


def test_prefix_consistency():
    """Running a prefix of length k gives the same first-k outputs as the full seq."""
    torch.manual_seed(1)
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=24, num_heads=3)).eval()
    x = torch.randn(2, 12, 24)
    y_full = layer(x)
    for k in (1, 3, 7, 12):
        y_prefix = layer(x[:, :k])
        diff = (y_full[:, :k] - y_prefix).abs().max().item()
        assert diff < 1e-6, f"prefix {k} mismatch {diff}"
