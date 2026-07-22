"""Attention-health and stability diagnostics (read-only).

All metrics operate on frozen trained models via forward passes; nothing here trains or
mutates the model.  They cover the reported quantities and the Guardrail-2 health checks:

  * attention entropy      -- normalised candidate-softmax entropy at query positions.
  * head diversity         -- mean pairwise symmetric-JS between the per-head candidate
                              distributions (0 => heads collapsed to one function).
  * head specialization    -- spread (std across heads) of per-head selection accuracy and of
                              per-head entropy (0 => heads indistinguishable).
  * perturbation stability -- 1 - normalised same-head JS between original and a
                              semantically-equivalent perturbed view (higher => more stable).
  * retrieval stability    -- fraction of (query, head) whose argmax candidate is unchanged
                              across the perturbation (behavioural, not correctness).
  * selection accuracy     -- argmax candidate == correct key (a DIAGNOSTIC; never trained on).

Guardrail-2 rejects a run whose attention organisation is unhealthy: entropy collapse,
(near-)uniform attention, head collapse, or loss of specialization.
"""

from __future__ import annotations

import math
from typing import Dict, List

import torch
import torch.nn.functional as F

from . import _qgr_path  # noqa: F401
from qgr.mqar import MQARConfig, generate_batch, split_seed
from qgr.metrics import evaluate

from .perturbations import AugConfig, make_aligned_pair
from .consistency import candidate_attention, gather_candidate_scores, js_divergence


@torch.no_grad()
def _per_head_candidate_probs(model, batch, aux_layer):
    """Return, for every query in the batch, per-head candidate distributions + correct idx.

    Yields dicts with 'probs' [H, C] (softmax over that query's candidates) and 'correct' int
    (index of the correct key within the candidate list, or -1).  Candidate count C varies by
    query; correctness is used ONLY for the selection-accuracy diagnostic.
    """
    out = model(batch.tokens, expose_quad=True)
    score = out["quad_score"]                      # [B,H,N,N]
    H = score.shape[1]
    qmask = batch.key_pos >= 0
    items = []
    for bi, t in qmask.nonzero(as_tuple=False).tolist():
        cand = batch.cand_mask[bi, t].nonzero(as_tuple=False).flatten()
        if cand.numel() == 0:
            continue
        s = score[bi, :, t, :][:, cand]             # [H, C]
        probs = F.softmax(s, dim=-1)                # [H, C]
        kp = int(batch.key_pos[bi, t])
        correct = int((cand == kp).nonzero(as_tuple=False).flatten()[0]) if (cand == kp).any() else -1
        items.append({"probs": probs, "correct": correct, "C": cand.numel()})
    return items, H


@torch.no_grad()
def attention_health(model, mq: MQARConfig, seed: int, split="test", n_batches=6,
                     batch_size=32) -> Dict[str, float]:
    """Entropy, head diversity, head specialization, selection accuracy on a config."""
    aux = model._aux_layer
    ent_norm_all: List[float] = []              # normalised entropy (head-mean per query)
    per_head_ent: List[List[float]] = []        # [query][head]
    per_head_correct: List[List[int]] = []      # [query][head] argmax==correct?
    inter_head_js: List[float] = []             # mean pairwise JS per query
    for i in range(n_batches):
        b = generate_batch(mq, split_seed(seed, split, i), batch_size)
        items, H = _per_head_candidate_probs(model, b, aux)
        for it in items:
            probs = it["probs"]                 # [H,C]
            C = it["C"]
            logC = math.log(max(C, 2))
            ent = -(probs.clamp_min(1e-12) * probs.clamp_min(1e-12).log()).sum(-1)  # [H]
            ent_norm_all.append(float(ent.mean()) / logC)
            per_head_ent.append([float(e) / logC for e in ent])
            am = probs.argmax(-1)               # [H]
            per_head_correct.append([int(int(a) == it["correct"]) for a in am])
            # pairwise inter-head JS (head diversity)
            if H > 1:
                js_sum, cnt = 0.0, 0
                for a in range(H):
                    for c in range(a + 1, H):
                        js_sum += float(js_divergence(probs[a], probs[c]))
                        cnt += 1
                inter_head_js.append(js_sum / max(cnt, 1))
    # aggregate
    mean_entropy = _mean(ent_norm_all)
    head_diversity = _mean(inter_head_js)
    # per-head selection accuracy (mean over queries for each head), then spread across heads
    if per_head_correct:
        H = len(per_head_correct[0])
        head_sel_acc = [ _mean([row[h] for row in per_head_correct]) for h in range(H) ]
        head_ent_mean = [ _mean([row[h] for row in per_head_ent]) for h in range(H) ]
        specialization_sel = _std(head_sel_acc)
        specialization_ent = _std(head_ent_mean)
        best_head_sel = max(head_sel_acc)
        headmean_sel = _mean([_mean(row) for row in per_head_correct])
    else:
        head_sel_acc = []; head_ent_mean = []
        specialization_sel = specialization_ent = best_head_sel = headmean_sel = float("nan")
    return {
        "attn_entropy_norm": mean_entropy,
        "head_diversity_js": head_diversity,
        "head_specialization_sel_std": specialization_sel,
        "head_specialization_ent_std": specialization_ent,
        "best_head_select_acc": best_head_sel,
        "headmean_select_acc": headmean_sel,
        "per_head_select_acc": head_sel_acc,
        "per_head_entropy_norm": head_ent_mean,
    }


@torch.no_grad()
def stability(model, mq: MQARConfig, seed: int, aug: AugConfig, split="test",
              n_batches=6, batch_size=32) -> Dict[str, float]:
    """Perturbation stability and retrieval stability under semantic-equivalence perturbations."""
    js_vals: List[float] = []
    same_argmax: List[float] = []
    C_ref = mq.num_kv * max(mq.n_relation_systems, 1)
    logC = math.log(max(C_ref, 2))
    for i in range(n_batches):
        base = generate_batch(mq, split_seed(seed, split, i), batch_size)
        pair = make_aligned_pair(base, mq, aug, seed=split_seed(seed, split, i) + 91)
        quad_o = model(pair.tokens_o, expose_quad=True)["quad_score"]
        quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
        p_o = candidate_attention(quad_o, pair.q_idx_o, pair.k_idx_o)   # [B,H,Q,K]
        p_p = candidate_attention(quad_p, pair.q_idx_p, pair.k_idx_p)
        js = js_divergence(p_o, p_p)                                    # [B,H,Q]
        js_vals.append(float(js.mean()))
        same = (p_o.argmax(-1) == p_p.argmax(-1)).float().mean()
        same_argmax.append(float(same))
    mean_js = _mean(js_vals)
    return {
        "perturb_stability": 1.0 - mean_js / logC,     # 1 == identical distributions
        "mean_perturb_js": mean_js,
        "retrieval_stability": _mean(same_argmax),     # fraction argmax unchanged
    }


def guardrail2_health(health: Dict[str, float],
                      entropy_floor=0.03, uniform_ceiling=0.995,
                      diversity_floor=0.005, specialization_floor=0.005) -> Dict:
    """Guardrail-2: reject runs with unhealthy attention organisation.

    Thresholds are pre-registered.  A run is UNHEALTHY if any holds:
      * entropy collapse : normalised entropy < entropy_floor (peaked to ~one key).
      * uniform attention: normalised entropy > uniform_ceiling AND head diversity ~0
                           (structureless uniform over candidates).
      * head collapse    : head diversity < diversity_floor (all heads identical).
      * loss of special. : BOTH selection-acc spread and entropy spread < specialization_floor.
    """
    e = health["attn_entropy_norm"]
    div = health["head_diversity_js"]
    ssel = health["head_specialization_sel_std"]
    sent = health["head_specialization_ent_std"]
    checks = {
        "entropy_collapse": bool(e < entropy_floor),
        "uniform_attention": bool(e > uniform_ceiling and div < diversity_floor),
        "head_collapse": bool(div < diversity_floor),
        "loss_of_specialization": bool(ssel < specialization_floor and sent < specialization_floor),
    }
    healthy = not any(checks.values())
    return {"healthy": healthy, "checks": checks,
            "entropy_norm": e, "head_diversity": div,
            "specialization_sel_std": ssel, "specialization_ent_std": sent}


def _mean(x: List[float]) -> float:
    return float(sum(x) / len(x)) if x else float("nan")


def _std(x: List[float]) -> float:
    if len(x) < 2:
        return 0.0
    m = _mean(x)
    return float((sum((v - m) ** 2 for v in x) / len(x)) ** 0.5)
