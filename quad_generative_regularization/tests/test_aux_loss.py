"""Auxiliary loss behavior and gradients (spec section 22 items 12-14)."""
import torch
from qgr import QuadConfig, build_model
from qgr.losses import quad_aux_loss, task_loss
from qgr.mqar import MQARConfig, generate_batch


def _setup():
    cfg = QuadConfig(vocab_size=48, hidden_size=48, num_layers=2, num_heads=4,
                     ff_size=192, context_length=64)
    m = build_model(cfg, 0)
    mq = MQARConfig(num_kv=8, num_queries=4, vocab_size=48)
    b = generate_batch(mq, seed=1, batch_size=4)
    return cfg, m, b


def test_lower_aux_when_correct_key_preferred():
    """Item 12: aux loss is lower when the correct key receives the higher Quad score."""
    _, m, b = _setup()
    out = m(b.tokens, expose_quad=True)
    base = float(quad_aux_loss(out["quad_score"], b.key_pos, b.cand_mask))
    # Construct an idealized score that strongly prefers the correct key per query.
    s = out["quad_score"].clone()
    score_bnn = s.mean(dim=1)
    ideal = torch.full_like(score_bnn, -10.0)
    q = b.key_pos >= 0
    for bi, t in q.nonzero(as_tuple=False).tolist():
        kp = int(b.key_pos[bi, t])
        ideal[bi, t] = torch.where(b.cand_mask[bi, t], torch.full_like(ideal[bi, t], -10.0), ideal[bi, t])
        ideal[bi, t, kp] = 10.0  # correct key strongly preferred
    ideal_score = ideal.unsqueeze(1).expand_as(s)
    better = float(quad_aux_loss(ideal_score, b.key_pos, b.cand_mask))
    assert better < base


def test_nonzero_aux_gradient_into_shared_params():
    """Item 13: aux gradient is nonzero on shared model parameters (embeddings, blocks)."""
    _, m, b = _setup()
    out = m(b.tokens, expose_quad=True)
    al = quad_aux_loss(out["quad_score"], b.key_pos, b.cand_mask)
    al.backward()
    emb_g = m.token_emb.weight.grad
    wq_g = m.blocks[m._aux_layer].attn.W_q.weight.grad
    assert emb_g is not None and emb_g.abs().sum() > 0     # reaches shared embeddings
    assert wq_g is not None and wq_g.abs().sum() > 0       # reaches Quad projection


def test_zero_aux_contribution_when_lambda_zero():
    """Item 14: total = task + 0*aux has gradients identical to task-only."""
    _, m, b = _setup()
    # task-only grads
    out1 = m(b.tokens, expose_quad=True)
    l1 = task_loss(out1["logits"], b.targets)
    g_task = torch.autograd.grad(l1, list(m.parameters()), retain_graph=False, allow_unused=True)
    # task + 0*aux grads
    out2 = m(b.tokens, expose_quad=True)
    l2 = task_loss(out2["logits"], b.targets) + 0.0 * quad_aux_loss(
        out2["quad_score"], b.key_pos, b.cand_mask)
    g_both = torch.autograd.grad(l2, list(m.parameters()), retain_graph=False, allow_unused=True)
    for a, c in zip(g_task, g_both):
        if a is None and c is None:
            continue
        assert torch.equal(a, c)   # bit-identical
