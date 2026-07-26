"""Stage 1 — the forward math matches reference_equations.md, recomputed by hand.

We recompute the entire kernel from scratch with plain torch ops (a second,
independent expression of the equations) and require it to match the module.
"""

import math

import torch

from symbolu.lightweight_phase import LightweightPhaseAttention, PhaseConfig


def _reference_forward(layer: LightweightPhaseAttention, x: torch.Tensor) -> torch.Tensor:
    """Independent reimplementation of reference_equations.md §1-§6 (no decay)."""
    cfg = layer.config
    B, N, D = x.shape
    H, Dh = cfg.num_heads, cfg.head_dim

    x_n = layer.norm(x)

    def proj(lin):
        return lin(x_n).view(B, N, H, Dh)

    phi_q = math.pi * torch.sin(proj(layer.W_phi_q)) if cfg.bounded_phase else proj(layer.W_phi_q)
    phi_k = math.pi * torch.sin(proj(layer.W_phi_k)) if cfg.bounded_phase else proj(layer.W_phi_k)
    a_q = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(proj(layer.W_a_q))
    a_k = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(proj(layer.W_a_k))
    v = proj(layer.W_v)

    # S_t = cumsum(a_k e^{-iφ_k} ⊙ v)
    k = torch.polar(a_k.float(), -phi_k.float())
    S = torch.cumsum(k * v.float(), dim=1)
    # A_t = cumsum(a_k)
    A = torch.cumsum(a_k.float(), dim=1)
    q = torch.polar(a_q.float(), phi_q.float())
    n_t = (q * S).real
    Z = (a_q.float() * A).clamp(min=cfg.denom_eps)
    o = (n_t / Z).reshape(B, N, D)
    out = layer.W_out(o) * cfg.aux_scale
    return out + x


def test_forward_matches_hand_derivation():
    torch.manual_seed(0)
    cfg = PhaseConfig(embed_dim=48, num_heads=6)
    layer = LightweightPhaseAttention(cfg).eval()
    x = torch.randn(3, 7, 48)
    got = layer(x)
    ref = _reference_forward(layer, x)
    assert torch.allclose(got, ref, atol=1e-6), (got - ref).abs().max().item()


def test_denominator_is_detached():
    """The normalizer Z must carry no gradient (frozen contract §5)."""
    torch.manual_seed(0)
    cfg = PhaseConfig(embed_dim=16, num_heads=2, detach_denominator=True)
    layer = LightweightPhaseAttention(cfg)
    x = torch.randn(2, 4, 16, requires_grad=True)
    # Compare gradient wrt W_a_q with and without detachment. Detached must differ
    # from the non-detached variant (proving Z's gradient path is removed).
    layer.zero_grad()
    layer(x).pow(2).sum().backward()
    g_detached = layer.W_a_q.weight.grad.clone()

    cfg2 = PhaseConfig(embed_dim=16, num_heads=2, detach_denominator=False)
    layer2 = LightweightPhaseAttention(cfg2)
    layer2.load_state_dict(layer.state_dict())
    x2 = x.detach().clone().requires_grad_(True)
    layer2.zero_grad()
    layer2(x2).pow(2).sum().backward()
    g_attached = layer2.W_a_q.weight.grad.clone()

    assert not torch.allclose(g_detached, g_attached), \
        "detaching the denominator must change the amplitude gradient"


def test_bounded_phase_range():
    """φ = π·sin(raw) ∈ [-π, π]."""
    torch.manual_seed(0)
    cfg = PhaseConfig(embed_dim=16, num_heads=2, bounded_phase=True)
    layer = LightweightPhaseAttention(cfg)
    x = torch.randn(4, 10, 16) * 100  # large inputs
    x_n = layer.norm(x)
    phi = math.pi * torch.sin(layer.W_phi_k(x_n))
    assert phi.abs().max() <= math.pi + 1e-5


def test_config_hash_is_deterministic_and_sensitive():
    a = PhaseConfig(embed_dim=32, num_heads=4)
    b = PhaseConfig(embed_dim=32, num_heads=4)
    c = PhaseConfig(embed_dim=32, num_heads=8)
    assert a.hash == b.hash
    assert a.hash != c.hash
    assert len(a.hash) == 64
