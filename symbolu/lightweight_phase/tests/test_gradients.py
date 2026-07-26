"""Stage 1 — gradients are finite and flow to every parameter."""

import pytest
import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig


@pytest.mark.parametrize("decay", [
    {},
    dict(decay_mode="fixed_scalar", gamma_min=0.5, gamma_max=1.0, initial_gamma=0.9),
    dict(decay_mode="learned_per_head", gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95),
])
def test_grads_finite_and_present(decay):
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=32, num_heads=4, **decay))
    x = torch.randn(2, 8, 32, requires_grad=True)
    loss = layer(x).pow(2).mean()
    loss.backward()
    assert torch.isfinite(x.grad).all()
    for name, p in layer.named_parameters():
        assert p.grad is not None, f"no grad for {name}"
        assert torch.isfinite(p.grad).all(), f"non-finite grad for {name}"
        # every trainable projection should actually receive signal
        if any(k in name for k in ("W_phi", "W_a", "W_v", "W_out")):
            assert p.grad.abs().sum() > 0, f"zero grad for {name}"


def test_learned_decay_receives_gradient():
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(
        PhaseConfig(embed_dim=32, num_heads=4, decay_mode="learned_per_head",
                    gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95)
    )
    x = torch.randn(2, 12, 32)
    layer(x).pow(2).mean().backward()
    assert layer.decay_theta.grad is not None
    assert layer.decay_theta.grad.abs().sum() > 0


def test_gradient_flows_through_carried_state():
    """Gradients must flow across a chunk boundary via the carried state."""
    torch.manual_seed(0)
    layer = LightweightPhaseAttention(PhaseConfig(embed_dim=16, num_heads=2))
    x1 = torch.randn(1, 4, 16, requires_grad=True)
    x2 = torch.randn(1, 4, 16, requires_grad=True)
    out1 = layer(x1, return_state=True)
    out2 = layer(x2, initial_state=out1.state, return_state=True)
    out2.output.pow(2).mean().backward()
    # x1 feeds only the carried state; its grad proves cross-chunk flow.
    assert x1.grad is not None and x1.grad.abs().sum() > 0
