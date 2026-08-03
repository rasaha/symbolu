"""Task-specific routing diagnostics for slot formation. Aggregate utilization was insufficient
in PR #1300, so we measure the write->address->read loop directly on needle fact/query pairs:
write-read overlap, correct-slot rank, top-1/top-k agreement, write/read entropy, address-logit
margin, write-gate value, and per-group gradient norms. All bounded (M-dim), no N x N tensor.
"""
from __future__ import annotations

import math

import torch
import torch.nn.functional as F

import interventions as IV


@torch.no_grad()
def routing_diagnostics(model, vocab, T, distance=96, n=64, seed=4321):
    """Averaged write/read routing metrics on n needle pairs at a given distance. Uses the
    non-invasive capture hooks; requires install_capture_hooks(model) to have been called."""
    import random
    rng = random.Random(seed)
    x, fact_pos, query_pos = IV.aux_needle_batch(vocab, n, 160, rng, T, distances=(distance, distance))
    was_training = model.training
    model.eval()
    IV.enable_capture(model, True)
    _ = model(x)
    slots = model.slot_mixers()
    idx = torch.arange(n)
    per_layer = []
    for sm in slots:
        w = sm._sfs_waddr[idx, fact_pos]      # [n, M] write dist at fact
        r = sm._sfs_raddr[idx, query_pos]     # [n, M] read dist at query
        rlogit = sm._sfs_rlogit[idx, query_pos]  # [n, M]
        gate = sm._sfs_gate[idx, fact_pos, 0]    # [n]
        overlap = (w * r).sum(-1)                # [n]
        hw = w.argmax(-1)                        # [n] highest-write slot
        read_on_hw = r[idx, hw]                  # [n] read prob on highest-write slot
        # rank of highest-write slot under read weights (0 = read's top choice)
        order = r.argsort(-1, descending=True)   # [n, M]
        rank = (order == hw.unsqueeze(-1)).float().argmax(-1)  # [n]
        top1_agree = (hw == r.argmax(-1)).float()
        k = 3
        wtop = set_topk(w, k); rtop = set_topk(r, k)
        topk_agree = torch.tensor([len(wtop[i] & rtop[i]) / k for i in range(n)])
        w_ent = entropy(w); r_ent = entropy(r)
        # address-logit margin: top1 - top2 of the read logits
        top2 = rlogit.topk(2, dim=-1).values
        margin = (top2[:, 0] - top2[:, 1])
        per_layer.append({
            "write_read_overlap": overlap.mean().item(),
            "read_prob_on_highest_write_slot": read_on_hw.mean().item(),
            "rank_of_highest_write_slot_under_read": rank.float().mean().item(),
            "top1_slot_agreement": top1_agree.mean().item(),
            "topk_slot_agreement": topk_agree.mean().item(),
            "write_entropy": w_ent.mean().item(),
            "read_entropy": r_ent.mean().item(),
            "address_logit_margin": margin.mean().item(),
            "write_gate_at_fact": gate.mean().item(),
        })
    IV.enable_capture(model, False)
    if was_training:
        model.train()
    # model-level means
    keys = per_layer[0].keys()
    agg = {kk: float(sum(pl[kk] for pl in per_layer) / len(per_layer)) for kk in keys}
    agg["distance"] = distance
    agg["n_pairs"] = n
    agg["per_layer"] = per_layer
    return agg


def set_topk(p, k):
    top = p.topk(k, dim=-1).indices.tolist()
    return [set(row) for row in top]


def entropy(p, eps=1e-9):
    return -(p * (p + eps).log()).sum(-1)


def grad_norm_probe(model, vocab, T, seed=777, distance=96, n=32):
    """One diagnostic forward+backward on a fixed needle probe -> grad norms into slot keys /
    read proj / write proj / gate. Caller MUST opt.zero_grad() afterwards: these grads are for
    measurement only and must never reach opt.step()."""
    import random
    rng = random.Random(seed)
    xs, ys, ms = [], [], []
    for _ in range(n):
        x, pos, tgt = T.needle(160, vocab, rng, distance=distance)
        y = x.clone(); y[:-1] = x[1:]; y[-1] = vocab.pad
        m = torch.zeros(160, dtype=torch.bool); m[pos - 1] = True
        xs.append(x); ys.append(y); ms.append(m)
    x = torch.stack(xs); y = torch.stack(ys); mask = torch.stack(ms)
    was_training = model.training
    model.train()
    model.zero_grad(set_to_none=True)
    lo = model(x)
    sel = mask.reshape(-1)
    loss = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
    loss.backward()
    def gn(substr):
        tot = 0.0
        for name, p in model.named_parameters():
            if IV.SLOT_MARKER in name and substr in name and p.grad is not None:
                tot += p.grad.detach().norm().item() ** 2
        return math.sqrt(tot)
    out = {
        "grad_norm_slot_keys": gn("slot_keys"),
        "grad_norm_read_proj": gn("W_rq"),
        "grad_norm_write_proj": gn("W_wk"),
        "grad_norm_write_value": gn("W_wv"),
        "grad_norm_gate": gn("gate"),
        "probe_loss": loss.item(),
    }
    model.zero_grad(set_to_none=True)
    if not was_training:
        model.eval()
    return out
