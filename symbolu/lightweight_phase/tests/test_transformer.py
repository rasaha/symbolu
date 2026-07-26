"""Stage 5 — Phase Transformer LM: forward, loss, backward, generation, checkpoint."""

import copy

import pytest
import torch

from symbolu.lightweight_phase.config import PhaseConfig, TransformerConfig
from symbolu.lightweight_phase.phase_block import LightweightPhaseTransformerLM


def _lm(seed=0, **tkw):
    torch.manual_seed(seed)
    cfg = TransformerConfig(vocab_size=48, phase=PhaseConfig(embed_dim=32, num_heads=4),
                            num_layers=2, max_seq_len=64, **tkw)
    return LightweightPhaseTransformerLM(cfg)


def test_forward_and_loss_shapes():
    m = _lm()
    ids = torch.randint(0, 48, (2, 10))
    logits, loss = m(ids, labels=ids)
    assert logits.shape == (2, 10, 48)
    assert loss.dim() == 0 and torch.isfinite(loss)


def test_backward_finite():
    m = _lm()
    ids = torch.randint(0, 48, (2, 10))
    _, loss = m(ids, labels=ids)
    loss.backward()
    for n, p in m.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all(), n


def test_tied_embeddings():
    m = _lm(tie_embeddings=True)
    assert m.lm_head.weight is m.token_embed.weight
    m2 = _lm(tie_embeddings=False)
    assert m2.lm_head.weight is not m2.token_embed.weight


def test_generation_matches_full_scan():
    m = _lm().eval()
    prefix = torch.randint(0, 48, (3, 5))
    gen = m.generate(prefix, max_new_tokens=7)
    seq = prefix.clone()
    for _ in range(7):
        lg, _ = m(seq)
        seq = torch.cat([seq, lg[:, -1].argmax(-1, keepdim=True)], dim=1)
    assert torch.equal(gen, seq[:, 5:])


def test_checkpoint_save_load():
    m = _lm()
    ids = torch.randint(0, 48, (2, 8))
    y0, _ = m(ids)
    sd = copy.deepcopy(m.state_dict())
    m2 = _lm(seed=999)  # different init
    m2.load_state_dict(sd)
    y1, _ = m2(ids)
    assert torch.allclose(y0, y1, atol=1e-6)


def test_deterministic_initialization():
    a = _lm(seed=123)
    b = _lm(seed=123)
    for pa, pb in zip(a.parameters(), b.parameters()):
        assert torch.equal(pa, pb)


def test_parameter_count_stable():
    m = _lm()
    assert m.num_parameters() == sum(
        p.numel() for p in {id(p): p for p in m.parameters()}.values()
    )


def test_learns_a_trivial_pattern():
    """A tiny copy task: loss must decrease over a few steps (backprop is wired)."""
    torch.manual_seed(0)
    m = _lm()
    opt = torch.optim.Adam(m.parameters(), lr=1e-2)
    ids = torch.randint(0, 48, (4, 12))
    first = None
    for _ in range(30):
        opt.zero_grad()
        _, loss = m(ids, labels=ids)
        loss.backward()
        opt.step()
        if first is None:
            first = loss.item()
    assert loss.item() < first * 0.9, (first, loss.item())
