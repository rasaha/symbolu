"""Smoke + correctness checks for the clean-softmax experiment.

The critical check is test_causality_no_future_leak: every augmentation on the
LM-loss path must be causal, or the next-token comparison is contaminated.

Run:  python -m symbolu_neural.clean_softmax.test_clean
      (or pytest symbolu_neural/clean_softmax/test_clean.py)
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .config import ABLATIONS, get_ablation
from .model import SymbolUSoftmaxModel


def _cfg(name, vocab=40, d=32, L=16):
    cfg = get_ablation(name)
    cfg.backbone.vocab_size = vocab
    cfg.backbone.d_model = d
    cfg.backbone.n_layers = 1
    cfg.backbone.n_heads = 4
    cfg.backbone.max_seq = L
    return cfg


def test_shapes_and_backward():
    V, L = 40, 16
    for name in ABLATIONS:
        torch.manual_seed(0)
        model = SymbolUSoftmaxModel(_cfg(name, V, 32, L))
        ids = torch.randint(0, V, (2, L))
        aux = model(ids)
        assert aux["logits"].shape == (2, L, V), (name, aux["logits"].shape)
        loss = F.cross_entropy(aux["logits"].reshape(-1, V), ids.reshape(-1))
        loss.backward()
        assert any(p.grad is not None for p in model.parameters() if p.requires_grad), name
        print(f"PASS shapes/backward [{name}]")


def test_causality_no_future_leak():
    """Changing token at position p must NOT change logits at positions < p."""
    V, L, p = 40, 16, 8
    for name in ("entropy_refine", "memory", "full"):
        torch.manual_seed(0)
        model = SymbolUSoftmaxModel(_cfg(name, V, 32, L)).eval()
        ids = torch.randint(0, V, (3, L))
        ids2 = ids.clone()
        ids2[:, p] = (ids2[:, p] + 1) % V                 # perturb position p only
        with torch.no_grad():
            a = model(ids)["logits"][:, :p]
            b = model(ids2)["logits"][:, :p]
        max_diff = (a - b).abs().max().item()
        assert max_diff < 1e-5, f"[{name}] future leak: logits<{p} changed by {max_diff:.2e}"
        print(f"PASS causality [{name}] (max pre-p logit diff {max_diff:.1e})")


def test_refinement_active():
    """Refinement must measurably change the hidden state, and disabling it (same
    seed) must change the logits. Guards against the no-op regression."""
    from .augment import TypedHeadBank
    V, L = 40, 16
    torch.manual_seed(0)
    model = SymbolUSoftmaxModel(_cfg("entropy_refine", V, 32, L)).eval()
    ids = torch.randint(0, V, (2, L))
    with torch.no_grad():
        h = model.lm.hidden(ids)
        ent = TypedHeadBank.entropies(model.heads(h))
        refined, diag = model.refine(h, ent)
        dh = (refined - h).norm().item()
        # logits with refinement on vs off (refinement skipped)
        on = model.lm.logits(refined)
        off = model.lm.logits(h)
        dlogit = (on - off).abs().max().item()
    assert dh > 1e-2, f"refinement hidden delta {dh:.2e} too small (no-op regression)"
    assert dlogit > 1e-3, f"disabling refinement barely changes logits ({dlogit:.2e})"
    assert diag["residual_post_gate_norm"] > 1e-2
    print(f"PASS refinement active (Δhidden {dh:.3f}, Δlogit {dlogit:.3f}, "
          f"gate_mean {float(diag['gate_mean']):.3f})")


def test_param_overhead_positive():
    base = SymbolUSoftmaxModel(_cfg("baseline")).num_params()
    full = SymbolUSoftmaxModel(_cfg("full")).num_params()
    assert full > base
    print(f"PASS param overhead (baseline {base/1e3:.0f}k -> full {full/1e3:.0f}k)")


def _run_all():
    test_shapes_and_backward()
    test_causality_no_future_leak()
    test_refinement_active()
    test_param_overhead_positive()
    print("ALL CLEAN-SOFTMAX CHECKS PASSED")


if __name__ == "__main__":
    _run_all()
