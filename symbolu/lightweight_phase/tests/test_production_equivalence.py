"""Stage 4 — equivalence to the production PhaseAttentionLayer (standard mode).

Required result: max abs output difference ≤ 1e-5 in float32. Every supported
setting is checked for forward, gradients, and (for chunking) state evolution.
Divergent production-only features are documented in PHASE_EQUIVALENCE_REPORT.md
and are intentionally out of scope here.
"""

import pytest
import torch

pytest.importorskip("symbolu.phase_transformer")

from symbolu.lightweight_phase.equivalence import make_matched_pair
from symbolu.lightweight_phase.streaming import run_chunked

TOL = 1e-5


@pytest.mark.parametrize("B,N,D,H", [(1, 4, 32, 4), (2, 8, 48, 6), (3, 16, 64, 8)])
def test_forward_equivalence_no_decay(B, N, D, H):
    torch.manual_seed(0)
    prod, light = make_matched_pair(D, H)
    x = torch.randn(B, N, D)
    assert (prod(x) - light(x)).abs().max().item() <= TOL


@pytest.mark.parametrize("gamma", [0.9, 0.95, 0.99])
def test_forward_equivalence_fixed_decay(gamma):
    torch.manual_seed(0)
    prod, light = make_matched_pair(32, 4, decay_gamma=gamma)
    x = torch.randn(2, 12, 32)
    assert (prod(x) - light(x)).abs().max().item() <= TOL


def test_forward_equivalence_learned_decay():
    torch.manual_seed(0)
    prod, light = make_matched_pair(32, 8, learned_decay=True)
    x = torch.randn(2, 16, 32)
    assert (prod(x) - light(x)).abs().max().item() <= TOL


def test_gradient_equivalence():
    """Gradients wrt input match between production and lightweight."""
    torch.manual_seed(0)
    prod, light = make_matched_pair(32, 4)
    x = torch.randn(2, 8, 32)
    xp = x.clone().requires_grad_(True)
    xl = x.clone().requires_grad_(True)
    prod(xp).pow(2).sum().backward()
    light(xl).pow(2).sum().backward()
    assert (xp.grad - xl.grad).abs().max().item() <= 1e-4


def test_weight_gradient_equivalence_on_values():
    """Grad wrt value projection matches (v_proj ↔ W_v)."""
    torch.manual_seed(0)
    prod, light = make_matched_pair(32, 4)
    x = torch.randn(2, 6, 32)
    prod(x).pow(2).sum().backward()
    light(x).pow(2).sum().backward()
    gp = prod.v_proj.weight.grad
    gl = light.W_v.weight.grad
    assert (gp - gl).abs().max().item() <= 1e-4


def test_training_mode_equivalence_dropout_zero():
    """With dropout=0, train() and eval() agree between the two implementations."""
    torch.manual_seed(0)
    prod, light = make_matched_pair(32, 4)
    prod.train(); light.train()
    x = torch.randn(2, 8, 32)
    assert (prod(x) - light(x)).abs().max().item() <= TOL


def test_state_evolution_equivalence_via_chunking():
    """Production chunk-persistent state vs lightweight carried PhaseState.

    Both must reproduce the single-pass output when the sequence is split.
    """
    torch.manual_seed(0)
    prod, light = make_matched_pair(48, 6)
    x = torch.randn(2, 12, 48)

    # lightweight: chunked with carried state
    y_light_chunked = run_chunked(light, x, [5, 4, 3])

    # production: chunk-persistent via prev_state/prev_norm_state
    prev_state = None
    prev_norm = None
    outs = []
    pos = 0
    for cs in (5, 4, 3):
        chunk = x[:, pos:pos + cs]
        out, sd = prod(chunk, prev_state=prev_state, prev_norm_state=prev_norm, return_state=True)
        outs.append(out)
        prev_state = sd["final_state"]
        prev_norm = sd["final_norm_state"]
        pos += cs
    y_prod_chunked = torch.cat(outs, dim=1)

    # both chunked paths must match the lightweight single pass
    y_light_full = light(x)
    assert (y_light_chunked - y_light_full).abs().max().item() <= TOL
    assert (y_prod_chunked - y_light_full).abs().max().item() <= TOL
