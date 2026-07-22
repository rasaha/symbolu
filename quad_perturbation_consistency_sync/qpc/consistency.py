"""Perturbation-consistency objective (training-only, label-free).

The consistency loss compares, per attention head independently, the query's retrieval
distribution over canonical PAIR buckets between a base sample x and its semantic-equivalent
perturbation x_tilde. It supervises NO target key and encourages NO one-hot: it only asks that
the (model-generated) relational distribution be invariant to irrelevant structure. Gradient
flows through A(x) only; A(x_tilde) is stop-gradient (or an EMA-teacher output).
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def pair_distribution(score: torch.Tensor, bucket: torch.Tensor, qpos: torch.Tensor,
                      num_buckets: int) -> torch.Tensor:
    """score [B,H,N,N] (causal, pre-softmax) -> P [B,Q,H,num_buckets].

    For each query position, softmax over candidate positions (bucket>=0), then aggregate the
    attention mass by canonical bucket identity (pair index, or 'other' for distractor keys)."""
    B, H, N, _ = score.shape
    Q = qpos.shape[1]
    device = score.device
    P = score.new_zeros(B, Q, H, num_buckets)
    for b in range(B):
        cand = bucket[b] >= 0                                   # [N]
        if cand.sum() == 0:
            continue
        # one-hot bucket assignment [num_buckets, N]
        M = score.new_zeros(num_buckets, N)
        idx = cand.nonzero(as_tuple=False).flatten()
        M[bucket[b, idx], idx] = 1.0
        sq = score[b][:, qpos[b], :]                            # [H,Q,N]
        sq = sq.masked_fill(~cand.view(1, 1, N), float("-inf"))
        a = F.softmax(sq, dim=-1)                               # [H,Q,N]
        P[b] = torch.einsum("hqn,kn->qhk", a, M)                # [Q,H,num_buckets]
    return P


def js_divergence(p: torch.Tensor, q: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Symmetric Jensen-Shannon divergence over the last dim, mean over leading dims."""
    p = p.clamp_min(eps); q = q.clamp_min(eps)
    p = p / p.sum(-1, keepdim=True); q = q / q.sum(-1, keepdim=True)
    m = 0.5 * (p + q)
    kl_pm = (p * (p / m).log()).sum(-1)
    kl_qm = (q * (q / m).log()).sum(-1)
    return (0.5 * kl_pm + 0.5 * kl_qm).mean()


def consistency_loss(score_x: torch.Tensor, paired, score_xt: torch.Tensor,
                     partner_roll: int = 0) -> torch.Tensor:
    """JS(A(x), stopgrad(A(x_tilde))) averaged over heads/queries. partner_roll>0 rolls the
    x_tilde batch to pair each x with an UNRELATED sample (shuffled-pair control)."""
    Px = pair_distribution(score_x, paired.x_bucket, paired.x_qpos, paired.num_buckets)
    with torch.no_grad():
        Pxt = pair_distribution(score_xt, paired.xt_bucket, paired.xt_qpos, paired.num_buckets)
        if partner_roll:
            Pxt = torch.roll(Pxt, shifts=partner_roll, dims=0)
    return js_divergence(Px, Pxt.detach())


@torch.no_grad()
def distribution_drift(score_x, paired, score_xt) -> float:
    """Diagnostic: JS between x and x_tilde pair distributions (how much retrieval drifts)."""
    Px = pair_distribution(score_x, paired.x_bucket, paired.x_qpos, paired.num_buckets)
    Pxt = pair_distribution(score_xt, paired.xt_bucket, paired.xt_qpos, paired.num_buckets)
    return float(js_divergence(Px, Pxt))
