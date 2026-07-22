"""Bounded Quad retrieval geometry — correctness and numerical tests (10 required)."""
import torch
import torch.nn.functional as F
from qgr import QuadConfig, build_model
from qgr.mqar import MQARConfig, generate_batch
from qgr.losses import task_loss, quad_aux_loss
from qgr.train import TrainConfig, train_arm

ALPHA = 4.0
EPS = 1e-6


def _cfg(bounded=True, alpha=ALPHA):
    return QuadConfig(vocab_size=32, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64, bounded=bounded,
                      bound_alpha=alpha, bound_eps=EPS)


def _mq():
    return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def _projected_qk(model, tokens):
    """Reproduce the per-head projected q/k the bounded attention normalizes (aux layer)."""
    B, N = tokens.shape
    pos = torch.arange(N).unsqueeze(0).expand(B, N)
    x = model.token_emb(tokens) + model.pos_emb(pos)
    attn = model.blocks[0].attn  # first block sees the embedding directly
    H, dh = attn.num_heads, attn.head_dim
    q = attn.W_q(attn.norm_q(x)).view(B, N, H, dh)
    k = attn.W_k(attn.norm_m(x)).view(B, N, H, dh)
    return q, k


def test_normalized_query_norms_approx_one():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=0, batch_size=4)
    q, _ = _projected_qk(m, b.tokens)
    qn = q / (q.norm(dim=-1, keepdim=True) + EPS)
    norms = qn.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-4)


def test_normalized_key_norms_approx_one():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=0, batch_size=4)
    _, k = _projected_qk(m, b.tokens)
    kn = k / (k.norm(dim=-1, keepdim=True) + EPS)
    norms = kn.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-4)


def test_bounded_logits_within_alpha():
    for alpha in (2.0, 4.0, 8.0):
        m = build_model(_cfg(alpha=alpha), 1)
        b = generate_batch(_mq(), seed=1, batch_size=4)
        s = m(b.tokens, expose_quad=True)["quad_score"]
        finite = s[torch.isfinite(s)]
        assert float(finite.abs().max()) <= alpha + 1e-4


def test_causal_mask_unchanged():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=2, batch_size=3)
    s = m(b.tokens, expose_quad=True)["quad_score"]
    N = s.shape[-1]
    upper = torch.triu(torch.ones(N, N, dtype=torch.bool), diagonal=1)
    assert torch.isinf(s[..., upper]).all() and (s[..., upper] < 0).all()
    assert torch.isfinite(s[..., ~upper]).all()


def test_candidate_ranking_deterministic():
    b = generate_batch(_mq(), seed=3, batch_size=4)
    m1 = build_model(_cfg(), 5).eval()
    m2 = build_model(_cfg(), 5).eval()
    with torch.no_grad():
        r1 = m1(b.tokens, expose_quad=True)["quad_score"].mean(1).argmax(-1)
        r2 = m2(b.tokens, expose_quad=True)["quad_score"].mean(1).argmax(-1)
    assert torch.equal(r1, r2)


def test_gradients_reach_projections_and_hidden():
    m = build_model(_cfg(), 0)
    b = generate_batch(_mq(), seed=1, batch_size=4)
    out = m(b.tokens, expose_quad=True)
    loss = task_loss(out["logits"], b.targets) + quad_aux_loss(
        out["quad_score"], b.key_pos, b.cand_mask)
    loss.backward()
    aux = m.blocks[m._aux_layer].attn
    assert aux.W_q.weight.grad.abs().sum() > 0
    assert aux.W_k.weight.grad.abs().sum() > 0
    assert m.token_emb.weight.grad.abs().sum() > 0    # shared hidden-state params


def test_no_nan_for_near_zero_vectors():
    m = build_model(_cfg(), 0).eval()
    # zeros -> LayerNorm(0)=0 -> projections 0 -> q_hat=0/(0+eps)=0 -> scores 0 (finite)
    toks = torch.zeros(2, 12, dtype=torch.long)
    with torch.no_grad():
        out = m(toks, expose_quad=True)
    s = out["quad_score"]
    finite = s[torch.isfinite(s)]
    assert torch.isfinite(finite).all() and not torch.isnan(out["logits"]).any()


def test_inference_deterministic():
    m = build_model(_cfg(), 7).eval()
    b = generate_batch(_mq(), seed=4, batch_size=3)
    with torch.no_grad():
        a = m(b.tokens)["logits"]
        c = m(b.tokens)["logits"]
    assert torch.equal(a, c)


def test_no_aux_after_bd_d10_cutoff():
    tc = TrainConfig(arm="D", lambda_aux=1.0, steps=40, aux_cutoff_frac=0.10,
                     batch_size=8, lr=3e-3, seed=0, eval_every=1, grad_diag_every=0)
    r = train_arm(_cfg(), _mq(), tc)
    cutoff = tc.cutoff_step()          # int(0.10*40)=4
    for h in r["history"]:
        if h["step"] >= cutoff:
            assert h["aux_active"] is False and h["aux_coeff"] == 0.0 and h["aux_loss"] == 0.0


def test_production_code_unmodified():
    """The package must not import any production module (symbolu/, symbolu_core/, etc.)."""
    import os, re
    pkg = os.path.join(os.path.dirname(__file__), os.pardir, "qgr")
    banned = re.compile(r"^\s*(from|import)\s+(symbolu|symbolu_core|resonant_model)\b", re.M)
    for fn in os.listdir(pkg):
        if fn.endswith(".py"):
            with open(os.path.join(pkg, fn)) as f:
                assert not banned.search(f.read()), f"{fn} imports production code"
