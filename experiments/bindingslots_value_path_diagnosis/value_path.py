#!/usr/bin/env python3
"""A1 (slot-value integrity), A3 (oracle correct-slot address) and A4 (oracle value-path reads).

All measurements run on FROZEN reproduced checkpoints with the model in eval mode and zero optimizer
steps. Oracle interventions modify ONLY the read vector at the query position (via the isolated
instrumented forward in diagnosis_lib); W_o, the residual add, backbone and decoder are untouched.
For collapsed seeds (ordinary needle already 0) the randomized-address / slots-off style ablations
are non-informative and are NOT used as causal evidence here; the oracle bypasses are.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

import diagnosis_lib as DL

EVAL_SEED = 123          # the committed needle eval seed (the ACTUAL failed evaluation examples)
EVAL_N = 120
EVAL_DISTANCE = 96


def _eval_examples(vocab, T):
    return DL.needle_examples(vocab, T, EVAL_SEED, EVAL_N, EVAL_DISTANCE)


def _capture(model, X, fp, qp, bs=60):
    """Collect the compact per-layer value-path tensors over the eval examples."""
    L = len(model.slot_mixers())
    acc = [{} for _ in range(L)]
    keys = ["sstar", "v_fact", "waddr_fact", "raddr_query", "read_query", "c_mem_query",
            "m_postwrite", "m_query", "read_prob_on_sstar", "w_to_sstar", "gate_fact"]
    parts = [[[] for _ in keys] for _ in range(L)]
    for i in range(0, len(X), bs):
        fb, qb = fp[i:i + bs], qp[i:i + bs]
        with DL.instrumented_model(model, mode=None, capture=True, fact_pos=fb, query_pos=qb) as slots:
            with torch.no_grad():
                _ = model(X[i:i + bs])
            for li, sm in enumerate(slots):
                for ki, k in enumerate(keys):
                    parts[li][ki].append(sm._cap[k])
    for li in range(L):
        for ki, k in enumerate(keys):
            acc[li][k] = torch.cat(parts[li][ki])
    return acc


def slot_value_integrity(model, vocab, T):
    """A1: for s*, compare m_postwrite vs m_query. Cosine, normalized L2 drift, norm ratio,
    sign-change rate, saturation, later-write count, explicit-overwrite flag. Per layer + last."""
    X, fp, qp, tgt = _eval_examples(vocab, T)
    caps = _capture(model, X, fp, qp)
    per_layer = []
    for li, c in enumerate(caps):
        post, quer = c["m_postwrite"], c["m_query"]
        cos = F.cosine_similarity(post, quer, dim=-1)              # [B]
        drift = (quer - post).norm(dim=-1) / (post.norm(dim=-1) + 1e-9)
        norm_ratio = quer.norm(dim=-1) / (post.norm(dim=-1) + 1e-9)
        sign_change = ((post.sign() != quer.sign()) & (post.abs() > 1e-6)).float().mean(dim=-1)
        # saturation: fraction of dims near the empirical max magnitude (proxy for clipping)
        mx = quer.abs().max(dim=-1, keepdim=True).values + 1e-9
        saturated = (quer.abs() > 0.98 * mx).float().mean(dim=-1)
        # later writes to s* strictly after the fact position
        B, Nn = c["w_to_sstar"].shape
        pos_idx = torch.arange(Nn).unsqueeze(0)
        after = pos_idx > fp.unsqueeze(1)
        w_after = c["w_to_sstar"] * after.float()
        n_later = (w_after > 0.05).sum(dim=-1).float()             # count of appreciable later writes
        max_later = w_after.max(dim=-1).values
        w_at_fact = c["w_to_sstar"].gather(1, fp.view(-1, 1)).squeeze(1)
        overwritten = (max_later > w_at_fact).float()             # a later token wrote more mass
        per_layer.append({
            "layer": li,
            "cosine_postwrite_query_mean": cos.mean().item(),
            "cosine_postwrite_query_min": cos.min().item(),
            "normalized_l2_drift_mean": drift.mean().item(),
            "norm_ratio_query_over_postwrite_mean": norm_ratio.mean().item(),
            "sign_change_rate_mean": sign_change.mean().item(),
            "saturation_fraction_mean": saturated.mean().item(),
            "n_later_writes_to_sstar_mean": n_later.mean().item(),
            "explicit_overwrite_fraction": overwritten.mean().item(),
            "write_gate_at_fact_mean": c["gate_fact"].mean().item(),
            "read_prob_on_sstar_mean": c["read_prob_on_sstar"].mean().item(),
        })
    last = per_layer[-1]
    return {"distance": EVAL_DISTANCE, "n": len(X), "per_layer": per_layer,
            "summary_last_layer": last,
            "primary_question": "does the correct slot still contain a recoverable representation of "
                                "the written fact at query time (A2 answers decodability; A1 the drift)"}


def _cmem_answer_alignment(model, X, fp, qp, tgt, mode, bs=60):
    """Mean cosine of the last-layer memory contribution c_mem at the query position with the
    correct-answer unembedding direction (head.weight[target]), under the given oracle mode; plus
    the memory-contribution norm."""
    head_w = model.head.weight.detach()   # [V, D] (tied to tok embedding)
    L = len(model.slot_mixers())
    cos_acc, norm_acc = [], []
    for i in range(0, len(X), bs):
        fb, qb, tb = fp[i:i + bs], qp[i:i + bs], tgt[i:i + bs]
        with DL.instrumented_model(model, mode=mode, capture=True, fact_pos=fb, query_pos=qb) as slots:
            with torch.no_grad():
                _ = model(X[i:i + bs])
            c_last = slots[-1]._cap["c_mem_query"]      # [b, D] (reflects the oracle read at qpos)
        dir_ans = head_w[tb]                            # [b, D]
        cos_acc.append(F.cosine_similarity(c_last, dir_ans, dim=-1))
        norm_acc.append(c_last.norm(dim=-1))
    return {"c_mem_answer_cosine_mean": torch.cat(cos_acc).mean().item(),
            "c_mem_norm_mean": torch.cat(norm_acc).mean().item()}


@torch.no_grad()
def _oracle_answer_metrics(model, X, fp, qp, tgt, mode, bs=60):
    """Needle acc + correct-answer logit margin under an oracle mode, binding the per-example
    positions per sub-batch (the oracle read override is per-example, so positions must match the
    batch actually passed through the forward)."""
    model.eval()
    n = len(X)
    correct = torch.zeros(n, dtype=torch.bool)
    margin = torch.zeros(n)
    for i in range(0, n, bs):
        xb, fb, qb, tb = X[i:i + bs], fp[i:i + bs], qp[i:i + bs], tgt[i:i + bs]
        with DL.instrumented_model(model, mode=mode, fact_pos=fb, query_pos=qb):
            lo = model(xb)
        j = torch.arange(len(xb))
        al = lo[j, qb]
        correct[i:i + bs] = (al.argmax(-1) == tb)
        tl = al[j, tb]
        al2 = al.clone(); al2[j, tb] = float('-inf')
        margin[i:i + bs] = tl - al2.max(-1).values
    return {"needle_acc": correct.float().mean().item(),
            "answer_logit_margin_mean": margin.mean().item(), "n": n}


def oracle_eval(model, vocab, T, mode, ordinary_ref=None):
    """A3/A4: run the needle eval on the ACTUAL failed examples under an oracle mode; report needle
    recovery, answer-logit margin, c_mem norm, c_mem-vs-answer alignment, and the delta vs ordinary.
    mode in {'oracle_address','oracle_read_query','oracle_postwrite'}."""
    X, fp, qp, tgt = _eval_examples(vocab, T)
    am = _oracle_answer_metrics(model, X, fp, qp, tgt, mode)
    align = _cmem_answer_alignment(model, X, fp, qp, tgt, mode)
    out = {"mode": mode, "distance": EVAL_DISTANCE, **am, **align}
    if ordinary_ref is not None:
        out["needle_delta_vs_ordinary"] = am["needle_acc"] - ordinary_ref["needle_acc"]
        out["margin_delta_vs_ordinary"] = am["answer_logit_margin_mean"] - ordinary_ref["answer_logit_margin_mean"]
    return out


def ordinary_eval(model, vocab, T):
    """Ordinary (no oracle) needle metrics on the failed eval examples + c_mem baseline alignment."""
    X, fp, qp, tgt = _eval_examples(vocab, T)
    with torch.no_grad():
        am = DL.answer_metrics(model, X, qp, tgt)
    align = _cmem_answer_alignment(model, X, fp, qp, tgt, mode=None)
    return {"mode": "ordinary", "distance": EVAL_DISTANCE, **am, **align}
