"""Tiny-dataset overfitting for Arms A, C, D (spec section 22 item 19, section 16 Phase 0B).

Failure to overfit a very small MQAR dataset is an implementation/optimization problem,
not a scientific result, so this is a required gate before the main run.
"""
import torch
from qgr import QuadConfig, build_model, GenericRelationHead
from qgr.mqar import MQARConfig, generate_batch, IGNORE_INDEX
from qgr.losses import task_loss, quad_aux_loss, generic_relational_loss


def _acc(model, batch):
    model.eval()
    with torch.no_grad():
        preds = model(batch.tokens)["logits"].argmax(-1)
    q = batch.targets != IGNORE_INDEX
    return float(((preds == batch.targets) & q).sum()) / float(q.sum())


def _overfit(arm, steps=400):
    cfg = QuadConfig(vocab_size=32, hidden_size=64, num_layers=2, num_heads=4,
                     ff_size=256, context_length=64)
    mq = MQARConfig(num_kv=4, num_queries=2, vocab_size=32)
    torch.manual_seed(0)
    model = build_model(cfg, 0)
    batch = generate_batch(mq, seed=123, batch_size=8)
    params = list(model.parameters())
    head = None
    if arm == "C":
        head = GenericRelationHead(cfg.hidden_size, cfg.num_heads)
        params = params + list(head.parameters())
    opt = torch.optim.AdamW(params, lr=3e-3)
    for _ in range(steps):
        model.train()
        out = model(batch.tokens, expose_quad=True, expose_hidden=True)
        loss = task_loss(out["logits"], batch.targets)
        if arm == "D":
            loss = loss + quad_aux_loss(out["quad_score"], batch.key_pos, batch.cand_mask)
        elif arm == "C":
            loss = loss + generic_relational_loss(head, out["aux_hidden"], batch.key_pos,
                                                  batch.cand_mask)
        opt.zero_grad(); loss.backward(); opt.step()
    return _acc(model, batch)


def test_overfit_arm_a():
    assert _overfit("A") > 0.95


def test_overfit_arm_c():
    assert _overfit("C") > 0.95


def test_overfit_arm_d():
    assert _overfit("D") > 0.95
