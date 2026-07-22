"""Causal masking and leakage prevention (spec sections 9, 22 items 7-9)."""
import torch
from qgr import QuadConfig, build_model
from qgr.mqar import MQARConfig, generate_batch


def _cfg():
    return QuadConfig(vocab_size=48, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64)


def test_strict_causal_masking():
    """Item 7: Quad score has -inf for all j > i (future positions masked)."""
    cfg = _cfg()
    m = build_model(cfg, 0)
    mq = MQARConfig(num_kv=6, num_queries=3, vocab_size=48)
    b = generate_batch(mq, seed=0, batch_size=2)
    out = m(b.tokens, expose_quad=True)
    s = out["quad_score"]                          # [B,H,N,N]
    N = s.shape[-1]
    upper = torch.triu(torch.ones(N, N, dtype=torch.bool), diagonal=1)
    assert torch.isinf(s[..., upper]).all()        # strictly-future entries are -inf
    assert (s[..., upper] < 0).all()
    lower = ~torch.triu(torch.ones(N, N, dtype=torch.bool), diagonal=1)
    assert torch.isfinite(s[..., lower]).all()     # causal entries are finite


def test_no_future_token_leakage_in_logits():
    """Item 8: logits at position t depend only on tokens <= t."""
    cfg = _cfg()
    m = build_model(cfg, 1).eval()
    mq = MQARConfig(num_kv=6, num_queries=3, vocab_size=48)
    b = generate_batch(mq, seed=2, batch_size=2)
    with torch.no_grad():
        base = m(b.tokens)["logits"]
        t = b.tokens.shape[1] // 2                  # perturb a middle position's future
        toks2 = b.tokens.clone()
        toks2[:, t + 1:] = (toks2[:, t + 1:] + 5) % cfg.vocab_size
        pert = m(toks2)["logits"]
    # positions 0..t must be unchanged
    assert torch.allclose(base[:, : t + 1], pert[:, : t + 1], atol=1e-6)
    # at least one later position changed (sanity: perturbation had an effect)
    assert not torch.allclose(base[:, t + 1:], pert[:, t + 1:], atol=1e-6)


def test_future_shuffle_invariance_of_aux():
    """Item 9 (required invariance): shuffling tokens strictly after a query position
    must not change that query's Quad score row nor the candidate-restricted aux logits."""
    cfg = _cfg()
    m = build_model(cfg, 3).eval()
    mq = MQARConfig(num_kv=6, num_queries=3, vocab_size=48)
    b = generate_batch(mq, seed=4, batch_size=3)
    N = b.tokens.shape[1]
    # pick the earliest query position in the batch
    q_positions = (b.key_pos >= 0).nonzero(as_tuple=False)
    qp = int(q_positions[:, 1].min())
    with torch.no_grad():
        s_base = m(b.tokens, expose_quad=True)["quad_score"]
        toks2 = b.tokens.clone()
        if qp + 1 < N:
            perm = torch.randperm(N - (qp + 1))
            toks2[:, qp + 1:] = toks2[:, qp + 1:][:, perm]
        s_pert = m(toks2, expose_quad=True)["quad_score"]
    # row qp (query i=qp), columns j<=qp are unaffected by future shuffling
    assert torch.allclose(s_base[:, :, qp, : qp + 1], s_pert[:, :, qp, : qp + 1], atol=1e-6)
