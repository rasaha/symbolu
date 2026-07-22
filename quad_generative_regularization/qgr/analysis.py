"""Read-only diagnostics for the Quad score dynamics analysis (analysis-only workstream).

Nothing here changes training or inference. Every function takes a model and a fixed batch
and returns JSON-friendly measurements:

  * quad_score_dynamics   - Phase 2/5: pos/neg/margin/entropy/variance + logit histogram
  * gradient_norms        - Phase 2: |dL_task/dS^Q|, |dL/dh|, |dL/dW_q|, |dL/dW_k|
  * representation_geometry - Phase 3/5: hidden cosine, projected q/k cosine, raw logits, probs
  * temperature_counterfactual - Phase 4: entropy/top1/margin/ranking under S^Q/T (offline)

All measurements are taken over QUERY positions, restricted to each query's causally-visible
candidate keys (correct key + earlier distractor keys), matching the deployed retrieval.
"""

from __future__ import annotations

from typing import Dict, List

import torch
import torch.nn.functional as F

from .losses import task_loss
from .mqar import MQARBatch


def _candidate_rows(score_bnn: torch.Tensor, key_pos: torch.Tensor, cand_mask: torch.Tensor):
    """Return (logits[P,N] candidate-masked to -inf off-candidates, target[P], pos-mask, neg-mask)."""
    qmask = key_pos >= 0
    rows = score_bnn[qmask]
    cand = cand_mask[qmask]
    tgt = key_pos[qmask]
    neg_inf = torch.finfo(rows.dtype).min
    masked = rows.masked_fill(~cand, neg_inf)
    pos_mask = torch.zeros_like(cand)
    pos_mask.scatter_(1, tgt.unsqueeze(1), True)
    neg_mask = cand & ~pos_mask
    return rows, masked, tgt, cand, pos_mask, neg_mask


@torch.no_grad()
def quad_score_dynamics(model, batch: MQARBatch, hist_range=(-60.0, 60.0), hist_bins=48) -> Dict:
    """Phase 2/5: distribution of the deployed Quad score over candidate keys."""
    out = model(batch.tokens, expose_quad=True)
    score_bnn = out["quad_score"].mean(dim=1)                 # [B,N,N] head-mean, as deployed
    rows, masked, tgt, cand, pos_mask, neg_mask = _candidate_rows(
        score_bnn, batch.key_pos, batch.cand_mask)
    pos = rows[pos_mask]                                       # correct-key logits
    neg = rows[neg_mask]                                       # distractor logits
    probs = F.softmax(masked, dim=1)
    ent = -(probs.clamp_min(1e-12) * probs.clamp_min(1e-12).log()).sum(1)
    top1 = probs.max(1).values
    # variance of candidate logits per query (finite candidates only)
    var_list = []
    for r in range(rows.shape[0]):
        c = cand[r]
        var_list.append(float(rows[r][c].var(unbiased=False)) if c.sum() > 1 else 0.0)
    all_cand_logits = rows[cand]
    hist = torch.histc(all_cand_logits.clamp(*hist_range), bins=hist_bins,
                       min=hist_range[0], max=hist_range[1])
    return {
        "pos_score_mean": float(pos.mean()), "neg_score_mean": float(neg.mean()),
        "margin_mean": float(pos.mean() - neg.mean()),
        "entropy_mean": float(ent.mean()), "top1_prob_mean": float(top1.mean()),
        "logit_variance_mean": float(sum(var_list) / max(len(var_list), 1)),
        "pos_score_std": float(pos.std()), "neg_score_std": float(neg.std()),
        "hist_counts": hist.tolist(), "hist_range": list(hist_range), "hist_bins": hist_bins,
        "n_queries": int((batch.key_pos >= 0).sum()),
    }


def gradient_norms(model, batch: MQARBatch) -> Dict:
    """Phase 2: task-loss gradient norms w.r.t. the Quad score, hidden state, and projections."""
    model.zero_grad(set_to_none=True)
    out = model(batch.tokens, expose_quad=True, expose_hidden=True)
    score = out["quad_score"]                 # non-leaf intermediate, in graph
    hidden = out["aux_hidden"]                # aux-layer input hidden state
    tl = task_loss(out["logits"], batch.targets)
    aux_block = model.blocks[model._aux_layer].attn
    inputs = [score, hidden, aux_block.W_q.weight, aux_block.W_k.weight]
    g_score, g_hidden, g_wq, g_wk = torch.autograd.grad(
        tl, inputs, retain_graph=False, allow_unused=True)
    def n(g):
        return float(g.norm()) if g is not None else 0.0
    return {
        "grad_wrt_score": n(g_score),
        "grad_wrt_hidden": n(g_hidden),
        "grad_wrt_Wq": n(g_wq),
        "grad_wrt_Wk": n(g_wk),
        "task_loss": float(tl),
    }


@torch.no_grad()
def representation_geometry(model, batch: MQARBatch) -> Dict:
    """Phase 3/5: where does separation originate — hidden geometry, projections, or softmax?

    For each query i and its candidates j, measure cosine similarity of:
      * raw hidden states  h_i vs h_j
      * projected queries/keys  (W_q LN h_i) vs (W_k LN h_j)  (the Quad projection space)
    and the resulting raw logits + normalized probs, split by correct vs distractor.
    """
    out = model(batch.tokens, expose_quad=True, expose_hidden=True)
    h = out["aux_hidden"]                                   # [B,N,D]
    attn = model.blocks[model._aux_layer].attn
    B, N, D = h.shape
    Hn, dh = attn.num_heads, attn.head_dim
    q = attn.W_q(attn.norm_q(h))                            # [B,N,D]
    k = attn.W_k(attn.norm_m(h))                            # [B,N,D]
    hn = F.normalize(h, dim=-1)
    qn = F.normalize(q, dim=-1)
    kn = F.normalize(k, dim=-1)

    hid_pos, hid_neg, qk_pos, qk_neg = [], [], [], []
    qmask = batch.key_pos >= 0
    for bi, t in qmask.nonzero(as_tuple=False).tolist():
        kp = int(batch.key_pos[bi, t])
        cand = batch.cand_mask[bi, t].nonzero(as_tuple=False).flatten().tolist()
        for j in cand:
            hc = float((hn[bi, t] * hn[bi, j]).sum())
            qkc = float((qn[bi, t] * kn[bi, j]).sum())
            if j == kp:
                hid_pos.append(hc); qk_pos.append(qkc)
            else:
                hid_neg.append(hc); qk_neg.append(qkc)
    m = lambda x: float(sum(x) / max(len(x), 1))
    return {
        "hidden_cos_pos": m(hid_pos), "hidden_cos_neg": m(hid_neg),
        "hidden_cos_gap": m(hid_pos) - m(hid_neg),
        "proj_qk_cos_pos": m(qk_pos), "proj_qk_cos_neg": m(qk_neg),
        "proj_qk_cos_gap": m(qk_pos) - m(qk_neg),
    }


@torch.no_grad()
def temperature_counterfactual(model, batch: MQARBatch,
                               temps=(1.0, 2.0, 5.0, 10.0, 20.0, 50.0)) -> Dict:
    """Phase 4: offline temperature sweep on the ALREADY-TRAINED logits (no retrain, no
    inference change). Distinguishes score collapse (logits diverged) from probability
    collapse (logits fine, softmax merely peaked): if even large T cannot restore entropy,
    the logits themselves have diverged. Ranking is temperature-invariant by construction."""
    out = model(batch.tokens, expose_quad=True)
    score_bnn = out["quad_score"].mean(dim=1)
    rows, masked, tgt, cand, pos_mask, neg_mask = _candidate_rows(
        score_bnn, batch.key_pos, batch.cand_mask)
    n_cand = cand.sum(1).float()
    max_entropy = n_cand.clamp(min=1).log().mean().item()     # uniform-over-candidates entropy
    base_rank = masked.argmax(1)
    res = {"max_entropy_uniform": max_entropy, "by_temp": {}}
    for T in temps:
        probs = F.softmax(masked / T, dim=1)
        ent = -(probs.clamp_min(1e-12) * probs.clamp_min(1e-12).log()).sum(1)
        top1 = probs.max(1).values
        rank = (masked / T).argmax(1)
        res["by_temp"][str(T)] = {
            "entropy_mean": float(ent.mean()),
            "entropy_frac_of_uniform": float(ent.mean()) / max(max_entropy, 1e-9),
            "top1_prob_mean": float(top1.mean()),
            "ranking_preserved": bool(torch.equal(rank, base_rank)),
        }
    return res


@torch.no_grad()
def projection_norms(model, batch: MQARBatch) -> Dict:
    """Phase 8: raw (pre-normalization) vs normalized projected query/key norms at the aux
    layer. For a bounded model the normalized norm is ~1; watching the RAW norm reveals whether
    training responds to the bound by inflating pre-normalization magnitudes (it cannot change
    the bounded score, so inflation would be a no-op escape attempt)."""
    out = model(batch.tokens, expose_hidden=True)
    h = out["aux_hidden"]
    attn = model.blocks[model._aux_layer].attn
    q = attn.W_q(attn.norm_q(h))
    k = attn.W_k(attn.norm_m(h))
    eps = getattr(attn, "bound_eps", 1e-6)
    return {
        "raw_q_norm": float(q.norm(dim=-1).mean()),
        "raw_k_norm": float(k.norm(dim=-1).mean()),
        "norm_q_normalized": float((q / (q.norm(dim=-1, keepdim=True) + eps)).norm(dim=-1).mean()),
        "norm_k_normalized": float((k / (k.norm(dim=-1, keepdim=True) + eps)).norm(dim=-1).mean()),
    }


def full_snapshot(model, batch: MQARBatch) -> Dict:
    """All read-only diagnostics at one training checkpoint."""
    snap = {}
    snap.update({f"dyn_{k}": v for k, v in quad_score_dynamics(model, batch).items()})
    snap.update({f"grad_{k}": v for k, v in gradient_norms(model, batch).items()})
    snap.update({f"geom_{k}": v for k, v in representation_geometry(model, batch).items()})
    snap.update({f"pnorm_{k}": v for k, v in projection_norms(model, batch).items()})
    snap["temp"] = temperature_counterfactual(model, batch)
    return snap
