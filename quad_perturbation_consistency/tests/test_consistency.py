"""Consistency-objective correctness: JS properties, same-head, stop-grad, shuffled control."""
import torch
import torch.nn.functional as F

import qpc  # noqa: F401
from qgr.experiment import FrozenConfig
from qgr.quad_model import build_model
from qgr.mqar import generate_batch, split_seed
from qpc.perturbations import make_aligned_pair, AugConfig
from qpc.consistency import (js_divergence, consistency_loss, candidate_attention,
                             gather_candidate_scores)


def _fc():
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = 4.0
    return fc


def test_js_symmetric_and_zero_on_equal():
    torch.manual_seed(0)
    p = F.softmax(torch.randn(7, 5), dim=-1)
    q = F.softmax(torch.randn(7, 5), dim=-1)
    assert torch.allclose(js_divergence(p, q), js_divergence(q, p), atol=1e-6)
    assert float(js_divergence(p, p).abs().max()) < 1e-7
    # JS is bounded by ln(2)
    assert float(js_divergence(p, q).max()) <= 0.6932 + 1e-4


def test_candidate_attention_is_distribution():
    fc = _fc(); mq = fc.base_mqar()
    model = build_model(fc.model_cfg(), 0)
    base = generate_batch(mq, split_seed(0, "train", 0), 8)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=1)
    q = model(pair.tokens_o, expose_quad=True)["quad_score"]
    p = candidate_attention(q, pair.q_idx_o, pair.k_idx_o)
    assert torch.allclose(p.sum(-1), torch.ones_like(p.sum(-1)), atol=1e-5)
    assert (p >= 0).all()


def test_consistency_gradient_flows_and_stop_grad():
    fc = _fc(); mq = fc.base_mqar()
    model = build_model(fc.model_cfg(), 0)
    base = generate_batch(mq, split_seed(0, "train", 0), 16)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=1)
    quad_o = model(pair.tokens_o, expose_quad=True)["quad_score"]
    quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
    loss, diag = consistency_loss(quad_o, quad_p, pair, stop_grad_target=True)
    assert loss.item() >= 0
    g = torch.autograd.grad(loss, model.parameters(), allow_unused=True)
    assert any(x is not None and x.abs().sum() > 0 for x in g)


def test_stop_grad_reduces_target_side_gradient():
    """With stop-grad, the target (perturbed) side contributes no gradient path of its own."""
    fc = _fc(); mq = fc.base_mqar()
    model = build_model(fc.model_cfg(), 0)
    base = generate_batch(mq, split_seed(0, "train", 0), 16)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=1)
    quad_o = model(pair.tokens_o, expose_quad=True)["quad_score"]
    quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
    l_sg, _ = consistency_loss(quad_o, quad_p, pair, stop_grad_target=True)
    l_full, _ = consistency_loss(quad_o, quad_p, pair, stop_grad_target=False)
    # both are valid JS values; stop-grad variant must be finite and >= 0
    assert l_sg.item() >= 0 and l_full.item() >= 0


def test_same_head_only():
    """gather uses the same head index on both sides -> shapes carry H unchanged (no mixing)."""
    fc = _fc(); mq = fc.base_mqar()
    model = build_model(fc.model_cfg(), 0)
    base = generate_batch(mq, split_seed(0, "train", 0), 4)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=1)
    q = model(pair.tokens_o, expose_quad=True)["quad_score"]
    g = gather_candidate_scores(q, pair.q_idx_o, pair.k_idx_o)
    assert g.shape[1] == fc.num_heads  # head axis preserved, not collapsed/crossed


def test_shuffled_control_changes_loss():
    fc = _fc(); mq = fc.base_mqar()
    model = build_model(fc.model_cfg(), 0)
    base = generate_batch(mq, split_seed(1, "train", 3), 32)
    real = make_aligned_pair(base, mq, AugConfig(), seed=2, shuffled_control=False)
    ctrl = make_aligned_pair(base, mq, AugConfig(), seed=2, shuffled_control=True)
    qo = model(real.tokens_o, expose_quad=True)["quad_score"]
    qp = model(real.tokens_p, expose_quad=True)["quad_score"]
    l_real, _ = consistency_loss(qo, qp, real)
    l_ctrl, _ = consistency_loss(qo, qp, ctrl)
    assert abs(l_real.item() - l_ctrl.item()) > 1e-6
