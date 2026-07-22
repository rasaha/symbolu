"""Tests for the perturbation-consistency track (validity, label-freeness, guardrail plumbing)."""
import torch
from qgr import QuadConfig, build_model, MQARConfig
from qgr.mqar import IGNORE_INDEX
from qpc.paired_mqar import gen_paired_batch, staged_partner
from qpc.consistency import pair_distribution, consistency_loss, js_divergence
from qpc.train_sync import SyncConfig, train_sync_arm


def _mq():
    return MQARConfig(num_kv=4, num_queries=2, vocab_size=32)


def _model(alpha=4.0):
    cfg = QuadConfig(vocab_size=32, hidden_size=48, num_layers=2, num_heads=4,
                     ff_size=192, context_length=64, bounded=True, bound_alpha=alpha)
    return build_model(cfg, 0)


def test_perturbation_preserves_answer():
    P = gen_paired_batch(_mq(), seed=1, batch_size=8)
    for b in range(8):
        xq = [int(P.x_tokens[b, int(q)]) for q in P.x_qpos[b]]
        tq = [int(P.xt_tokens[b, int(q)]) for q in P.xt_qpos[b]]
        assert xq == tq                                   # same queries (canonical order)
        for q in P.x_qpos[b]:
            assert P.x_targets[b, int(q)] != IGNORE_INDEX  # answer present at each query


def test_pair_distributions_normalize():
    P = gen_paired_batch(_mq(), seed=2, batch_size=6)
    m = _model()
    s = m(P.x_tokens, expose_quad=True)["quad_score"]
    Px = pair_distribution(s, P.x_bucket, P.x_qpos, P.num_buckets)
    assert torch.allclose(Px.sum(-1), torch.ones_like(Px.sum(-1)), atol=1e-4)


def test_consistency_loss_is_label_free():
    """The consistency loss must not depend on any retrieval label: permuting the (unused)
    correct-key labels leaves it unchanged."""
    P = gen_paired_batch(_mq(), seed=3, batch_size=6)
    m = _model()
    sx = m(P.x_tokens, expose_quad=True)["quad_score"]
    st = m(P.xt_tokens, expose_quad=True)["quad_score"]
    base = float(consistency_loss(sx, P, st))
    P.x_key_pos = torch.roll(P.x_key_pos, 1, 0)           # scramble labels
    P.x_cand_mask = torch.roll(P.x_cand_mask, 1, 0)
    after = float(consistency_loss(sx, P, st))
    assert base == after                                  # label-independent


def test_consistency_zero_for_identical_and_grad_flows():
    P = gen_paired_batch(_mq(), seed=4, batch_size=6, perturb=False)  # x == x_tilde
    m = _model()
    sx = m(P.x_tokens, expose_quad=True)["quad_score"]
    st = m(P.xt_tokens, expose_quad=True)["quad_score"]
    L = consistency_loss(sx, P, st)
    assert float(L) < 1e-5                                 # identical inputs -> ~0 divergence
    L2 = consistency_loss(sx, P, st)
    assert L2.requires_grad


def test_shuffled_pair_changes_target():
    P = gen_paired_batch(_mq(), seed=5, batch_size=8)
    m = _model()
    sx = m(P.x_tokens, expose_quad=True)["quad_score"]
    st = m(P.xt_tokens, expose_quad=True)["quad_score"]
    aligned = float(consistency_loss(sx, P, st, partner_roll=0))
    shuffled = float(consistency_loss(sx, P, st, partner_roll=1))
    assert aligned != shuffled                            # unrelated partner -> different target


def test_bd_a_sync_off_is_deterministic():
    cfg = SyncConfig(steps=20, eval_every=10**9, batch_size=8)
    r1 = train_sync_arm("BD-A", 0, cfg, log_curves=False)
    r2 = train_sync_arm("BD-A", 0, cfg, log_curves=False)
    p1, p2 = dict(r1["model"].named_parameters()), dict(r2["model"].named_parameters())
    for n in p1:
        assert torch.equal(p1[n], p2[n])


def test_sync_early_disables_after_cutoff():
    cfg = SyncConfig(steps=40, eval_every=1, batch_size=8, early_cutoff_frac=0.25)
    r = train_sync_arm("BD-Sync-Early", 0, cfg)
    cutoff = r["cutoff_step"]
    assert cutoff == 10
    for h in r["history"]:
        if h["step"] >= cutoff:
            assert h["aux_active"] is False and h["aux_loss"] == 0.0


def test_staged_partner_stage0_is_identity():
    P = staged_partner(_mq(), seed=6, batch_size=4, stage=0)
    assert torch.equal(P.x_tokens, P.xt_tokens)           # stage 0 = original
