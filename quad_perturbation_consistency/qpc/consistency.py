"""Same-head perturbation-consistency objective (no retrieval labels).

For a query, each attention head produces a distribution over the candidate keys.  The
objective asks: does head *h* produce the *same* distribution when the sequence is perturbed
by an irrelevant factor?  It penalises the **symmetric Jensen-Shannon divergence** between a
head's candidate-attention on the original view and on a semantically-equivalent view, with a
**stop-gradient (or EMA self-target) on the target side** and a **small fixed coefficient**.

Design constraints honoured (and deliberately NOT exceeded):
  * same-head only            -- head h(O) is compared to head h(P); never across heads/layers.
  * symmetric JSD             -- the divergence is the symmetric JS, not KL or L2.
  * stop-gradient / EMA target-- one side is detached (default) or produced by an EMA copy.
  * small fixed coefficient   -- lambda is a single frozen scalar.
  * no retrieval labels       -- alignment is by augmentation correspondence (token identity),
                                 not by which key is "correct"; the correct key is never used.
  * behavioural, not correct  -- the loss measures stability of the distribution, not whether
                                 it points at the right key.

Nothing here changes inference: the objective is a training-time addition read from the
model's *own* forward-path Quad score (the same tensor the deployed model already computes).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn.functional as F
from torch import Tensor

from .perturbations import AlignedPair


def gather_candidate_scores(quad_score: Tensor, q_idx: Tensor, k_idx: Tensor) -> Tensor:
    """Extract per-head candidate scores at canonical (query, key) positions.

    quad_score : [B,H,N,N] causal, pre-softmax Quad score (rows=query, cols=key).
    q_idx      : [B,Q] query positions (canonical order).
    k_idx      : [B,K] candidate-key positions (canonical order).
    returns    : [B,H,Q,K] raw scores S^Q[b,h,q_idx[b,q], k_idx[b,k]].
    """
    B, H, N, _ = quad_score.shape
    Q = q_idx.shape[1]
    K = k_idx.shape[1]
    rows = quad_score.gather(2, q_idx[:, None, :, None].expand(B, H, Q, N))   # [B,H,Q,N]
    cols = rows.gather(3, k_idx[:, None, None, :].expand(B, H, Q, K))         # [B,H,Q,K]
    return cols


def candidate_attention(quad_score: Tensor, q_idx: Tensor, k_idx: Tensor,
                        tau: float = 1.0) -> Tensor:
    """Per-head softmax over the candidate keys -> [B,H,Q,K] probability distributions.

    This restricts to and renormalises over the candidate set, exactly matching how the
    deployed retrieval selects among candidates; it is invariant to the (identical) set of
    non-candidate positions across the two views.
    """
    sc = gather_candidate_scores(quad_score, q_idx, k_idx)
    return F.softmax(sc / tau, dim=-1)


def js_divergence(p: Tensor, q: Tensor, eps: float = 1e-12) -> Tensor:
    """Symmetric Jensen-Shannon divergence along the last dim. p,q: [...,K] -> [...]."""
    m = 0.5 * (p + q)
    def kl(a, b):
        return (a * ((a + eps).log() - (b + eps).log())).sum(dim=-1)
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def consistency_loss(quad_o: Tensor, quad_p: Tensor, pair: AlignedPair, tau: float = 1.0,
                     stop_grad_target: bool = True) -> Tuple[Tensor, Dict[str, float]]:
    """Same-head symmetric-JS consistency between view O and view P.

    quad_o / quad_p : [B,H,N,N] Quad scores for the original / perturbed views.
    pair            : provides the canonical alignment indices and the (identity or shuffled)
                      key permutation applied to view P's key axis.
    Returns (scalar loss, diagnostics).  The gradient flows through the ORIGINAL side; the
    perturbed side is the (detached) target when stop_grad_target is True.
    """
    p_o = candidate_attention(quad_o, pair.q_idx_o, pair.k_idx_o, tau)            # [B,H,Q,K]
    # apply the key-axis permutation to view P (identity for the real objective; a random
    # permutation for the shuffled-pair control), then softmax.
    k_idx_p = pair.k_idx_p.gather(1, pair.key_perm)                               # [B,K]
    p_p = candidate_attention(quad_p, pair.q_idx_p, k_idx_p, tau)                 # [B,H,Q,K]

    target = p_p.detach() if stop_grad_target else p_p
    jsd = js_divergence(p_o, target)                                             # [B,H,Q]
    loss = jsd.mean()
    with torch.no_grad():
        diag = {
            "consistency_jsd": float(jsd.mean()),
            "consistency_jsd_max": float(jsd.max()) if jsd.numel() else 0.0,
        }
    return loss, diag


class EMATarget:
    """Optional EMA self-target: a shadow copy of the model producing the target view.

    Provided to satisfy the "EMA self-target" alternative to stop-gradient.  When used, the
    perturbed view is scored by the EMA copy (implicitly detached), so the target is a slow
    average of the model's own past behaviour rather than the current step's detached output.
    """

    def __init__(self, model, decay: float = 0.99):
        import copy
        self.decay = decay
        self.ema = copy.deepcopy(model).eval()
        for p in self.ema.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model):
        for pe, pm in zip(self.ema.parameters(), model.parameters()):
            pe.mul_(self.decay).add_(pm, alpha=1.0 - self.decay)
        for be, bm in zip(self.ema.buffers(), model.buffers()):
            be.copy_(bm)

    @torch.no_grad()
    def score(self, tokens: Tensor) -> Tensor:
        return self.ema(tokens, expose_quad=True)["quad_score"]
