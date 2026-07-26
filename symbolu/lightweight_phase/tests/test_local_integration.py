"""Stage 6 — sliding-window local path, protected additive fusion, instrumentation."""

import math

import pytest
import torch

from symbolu.lightweight_phase.config import PhaseConfig, TransformerConfig
from symbolu.lightweight_phase.local_window import LocalWindowAttention
from symbolu.lightweight_phase.phase_block import LightweightPhaseTransformerLM
from symbolu.lightweight_phase.diagnostics import path_contribution
from symbolu.lightweight_phase.invariants import shape_audit


def test_local_window_causal():
    torch.manual_seed(0)
    layer = LocalWindowAttention(32, 4, window=4).eval()
    x = torch.randn(1, 12, 32)
    y = layer(x)
    x2 = x.clone(); x2[:, 6:] = torch.randn(1, 6, 32)
    y2 = layer(x2)
    assert (y[:, :6] - y2[:, :6]).abs().max().item() < 1e-6


def test_local_window_matches_masked_reference():
    """Unfold sliding window == full masked softmax attention restricted to window."""
    torch.manual_seed(0)
    D, H, W, N = 32, 4, 4, 10
    layer = LocalWindowAttention(D, H, window=W).eval()
    x = torch.randn(1, N, D)
    got = layer(x, return_residual_add=False)

    # reference: full [N,N] masked attention (allowed in TEST only, not in the model)
    xn = layer.norm(x)
    q = layer.W_q(xn).view(1, N, H, D // H).transpose(1, 2)
    k = layer.W_k(xn).view(1, N, H, D // H).transpose(1, 2)
    v = layer.W_v(xn).view(1, N, H, D // H).transpose(1, 2)
    scores = (q @ k.transpose(-1, -2)) / math.sqrt(D // H)
    i = torch.arange(N).view(N, 1); j = torch.arange(N).view(1, N)
    mask = (j > i) | (i - j >= W)
    scores = scores.masked_fill(mask.view(1, 1, N, N), float("-inf"))
    attn = torch.softmax(scores, dim=-1)
    ref = (attn @ v).transpose(1, 2).reshape(1, N, D)
    ref = layer.W_out(ref)
    assert (got - ref).abs().max().item() < 1e-5


def test_local_window_is_subquadratic():
    """The local path registers only O(N·W) score tensors (n_seq_axes=1)."""
    layer = LocalWindowAttention(32, 4, window=4).eval()
    with shape_audit(seq_len=20):  # must not raise INV-NO-NN
        layer(torch.randn(1, 20, 32))


def test_protected_fusion_both_paths_active_at_init():
    cfg = TransformerConfig(vocab_size=48, phase=PhaseConfig(embed_dim=32, num_heads=4),
                            num_layers=1, use_local_window=True, local_window_size=6)
    m = LightweightPhaseTransformerLM(cfg)
    blk = m.blocks[0]
    assert blk.alpha_local.item() == 1.0 and blk.alpha_phase.item() == 1.0


def test_config_A_local_only_vs_B_local_plus_phase_differ():
    """Disabling the Phase path (config A) changes predictions vs A+Phase (config B)."""
    torch.manual_seed(0)
    ids = torch.randint(0, 48, (2, 16))

    base = TransformerConfig(vocab_size=48, phase=PhaseConfig(embed_dim=32, num_heads=4),
                             num_layers=2, use_local_window=True, local_window_size=6)
    torch.manual_seed(1)
    m = LightweightPhaseTransformerLM(base).eval()
    logits_B, _ = m(ids)

    # config A = zero the phase contribution by setting alpha_phase=0
    with torch.no_grad():
        for blk in m.blocks:
            blk.alpha_phase.zero_()
    logits_A, _ = m(ids)
    assert (logits_A - logits_B).abs().max().item() > 1e-4


def test_path_contribution_instrumentation():
    torch.manual_seed(0)
    D = 32
    local = LocalWindowAttention(D, 4, window=6).eval()
    x = torch.randn(2, 10, D)
    lo = local(x, return_residual_add=False)
    po = torch.randn_like(lo)
    info = path_contribution(lo, po)
    assert 0.0 <= info["phase_fraction"] <= 1.0
    assert abs(info["local_fraction"] + info["phase_fraction"] - 1.0) < 1e-5
