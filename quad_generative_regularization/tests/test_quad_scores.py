"""Quad score shapes and candidate filtering (spec section 22 items 10-11)."""
import torch
from qgr import QuadConfig, build_model
from qgr.losses import _candidate_rows
from qgr.mqar import MQARConfig, generate_batch


def test_quad_score_shape():
    """Item 10: Quad score is [B, H, N, N]."""
    cfg = QuadConfig(vocab_size=48, hidden_size=64, num_layers=3, num_heads=8,
                     ff_size=256, context_length=64)
    m = build_model(cfg, 0)
    mq = MQARConfig(num_kv=6, num_queries=3, vocab_size=48)
    b = generate_batch(mq, seed=0, batch_size=5)
    out = m(b.tokens, expose_quad=True)
    B, N = b.tokens.shape
    assert out["quad_score"].shape == (B, cfg.num_heads, N, N)
    assert "aux_hidden" not in out  # not requested -> key absent


def test_candidate_filtering():
    """Item 11: aux logits are finite only on candidate columns, -inf elsewhere."""
    cfg = QuadConfig(vocab_size=48, hidden_size=48, num_layers=2, num_heads=4,
                     ff_size=192, context_length=64)
    m = build_model(cfg, 0)
    mq = MQARConfig(num_kv=8, num_queries=4, vocab_size=48)
    b = generate_batch(mq, seed=1, batch_size=4)
    out = m(b.tokens, expose_quad=True)
    score_bnn = out["quad_score"].mean(dim=1)
    rows, tgt, valid = _candidate_rows(score_bnn, b.key_pos, b.cand_mask)
    assert valid
    cand_rows = b.cand_mask[b.key_pos >= 0]
    # Non-candidate columns (future j>i and past non-key positions) are masked to
    # finfo.min; candidate columns retain their original finite Quad score.
    neg_inf = torch.finfo(rows.dtype).min
    kept = rows != neg_inf
    assert torch.equal(kept, cand_rows)
    # target is always a candidate (kept, i.e. not masked out)
    assert (rows.gather(1, tgt.unsqueeze(1)) != neg_inf).all()
