"""Losses for the Quad generative regularization study.

* task_loss            : next-token cross-entropy at query positions (all arms).
* quad_aux_loss        : Option B (native) candidate classification on the authentic
                         Quad score S^Q (Arm D).
* generic_relational_loss : the SAME candidate classification, but on ordinary
                         hidden-state similarity <h_i, h_j>/sqrt(D) (Arm C control).
* quad_margin_loss     : Option C fallback (margin), retained for robustness only.

Arms C and D receive identical relational supervision (same query positions, same
positive key labels, same candidate sets, same causal restriction, same temperature);
they differ ONLY in which score field the loss reads.  This isolates whether supervising
the Quad-native score specifically helps beyond generic relational supervision.
"""

from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn.functional as F
from torch import Tensor

from .mqar import IGNORE_INDEX


def task_loss(logits: Tensor, targets: Tensor) -> Tensor:
    """Cross-entropy over query positions only (targets = IGNORE_INDEX elsewhere)."""
    B, N, V = logits.shape
    return F.cross_entropy(
        logits.reshape(B * N, V), targets.reshape(B * N), ignore_index=IGNORE_INDEX
    )


def _candidate_rows(score_bnn: Tensor, key_pos: Tensor, cand_mask: Tensor):
    """Extract candidate-classification rows at query positions.

    Returns (logits_rows [P,N], target_rows [P], valid) where P = number of query
    positions across the batch.  Non-candidate columns are set to -inf.
    """
    qmask = key_pos >= 0                       # [B,N] True at query positions
    if qmask.sum() == 0:
        return None, None, False
    logits_rows = score_bnn[qmask]             # [P,N] : S^Q_{i,.} for each query i
    cand_rows = cand_mask[qmask]               # [P,N] boolean
    target_rows = key_pos[qmask]               # [P]   correct key position j+
    # Restrict to candidate set (correct key + earlier distractor keys).
    neg_inf = torch.finfo(logits_rows.dtype).min
    logits_rows = logits_rows.masked_fill(~cand_rows, neg_inf)
    return logits_rows, target_rows, True


def quad_aux_loss(quad_score: Tensor, key_pos: Tensor, cand_mask: Tensor,
                  tau: float = 1.0) -> Tensor:
    """Option B — native Quad candidate classification.

    quad_score: [B,H,N,N] authentic Quad score (causal, pre-softmax).
    Mean over heads (matching get_proposals' head-mean), then softmax over the causally
    visible candidate keys and NLL of the correct earlier key.
    """
    score_bnn = quad_score.mean(dim=1)         # [B,N,N] (i=query row, j=key col)
    logits_rows, target_rows, valid = _candidate_rows(score_bnn, key_pos, cand_mask)
    if not valid:
        return quad_score.new_zeros(())
    return F.cross_entropy(logits_rows / tau, target_rows)


def generic_relational_loss(relation_head, aux_hidden: Tensor, key_pos: Tensor,
                            cand_mask: Tensor, tau: float = 1.0) -> Tensor:
    """Arm C control — candidate classification on an equal-capacity OFF-PATH relation.

    relation_head: GenericRelationHead producing a [B,H,N,N] score from hidden states.
    aux_hidden:    [B,N,D] hidden states feeding the aux layer (same layer Arm D reads).
    The head is training-only (discarded at inference) and does NOT use the Quad score,
    so this measures whether generic relational supervision — not Quad-native supervision —
    explains any improvement.
    """
    rel = relation_head(aux_hidden).mean(dim=1)   # [B,N,N]
    logits_rows, target_rows, valid = _candidate_rows(rel, key_pos, cand_mask)
    if not valid:
        return aux_hidden.new_zeros(())
    return F.cross_entropy(logits_rows / tau, target_rows)


def quad_margin_loss(quad_score: Tensor, key_pos: Tensor, cand_mask: Tensor,
                     margin: float = 1.0) -> Tensor:
    """Option C fallback — softplus margin between correct key and each distractor."""
    score_bnn = quad_score.mean(dim=1)
    qmask = key_pos >= 0
    if qmask.sum() == 0:
        return quad_score.new_zeros(())
    rows = score_bnn[qmask]                     # [P,N]
    cand = cand_mask[qmask]                     # [P,N]
    tgt = key_pos[qmask]                        # [P]
    pos = rows.gather(1, tgt.unsqueeze(1))      # [P,1] correct-key score
    neg_mask = cand.clone()
    neg_mask.scatter_(1, tgt.unsqueeze(1), False)  # distractors only
    diff = margin - pos + rows                  # [P,N]
    diff = diff.masked_fill(~neg_mask, float("-inf"))
    # log(1 + sum_j exp(diff_j)) via logsumexp with an implicit 0 term.
    zero = torch.zeros(diff.shape[0], 1, device=diff.device, dtype=diff.dtype)
    return torch.logsumexp(torch.cat([zero, diff], dim=1), dim=1).mean()


@torch.no_grad()
def mechanism_diagnostics(quad_score: Tensor, key_pos: Tensor, cand_mask: Tensor
                          ) -> Dict[str, float]:
    """Quad-score mechanism metrics over query positions (spec section 19)."""
    score_bnn = quad_score.mean(dim=1)          # [B,N,N]
    qmask = key_pos >= 0
    out = {
        "correct_key_score": float("nan"),
        "incorrect_key_score": float("nan"),
        "pos_neg_margin": float("nan"),
        "cand_entropy": float("nan"),
        "internal_select_acc": float("nan"),
    }
    if qmask.sum() == 0:
        return out
    rows = score_bnn[qmask]                      # [P,N]
    cand = cand_mask[qmask]                      # [P,N]
    tgt = key_pos[qmask]                         # [P]
    neg_inf = torch.finfo(rows.dtype).min
    masked = rows.masked_fill(~cand, neg_inf)

    pos = rows.gather(1, tgt.unsqueeze(1)).squeeze(1)              # [P]
    neg_mask = cand.clone().scatter(1, tgt.unsqueeze(1), False)    # distractors
    # Use a finite-safe masked sum: rows contains -inf at future (causal-masked) columns,
    # and 0 * (-inf) = NaN, so zero out non-selected entries with torch.where instead.
    rows_safe = torch.where(neg_mask, rows, torch.zeros_like(rows))
    neg_sum = rows_safe.sum(1)
    neg_cnt = neg_mask.sum(1).clamp(min=1)
    neg_mean = neg_sum / neg_cnt

    probs = F.softmax(masked, dim=1)
    ent = -(probs.clamp_min(1e-12) * probs.clamp_min(1e-12).log()).sum(1)
    pred = masked.argmax(1)
    acc = (pred == tgt).float()

    out["correct_key_score"] = pos.mean().item()
    out["incorrect_key_score"] = neg_mean.mean().item()
    out["pos_neg_margin"] = (pos - neg_mean).mean().item()
    out["cand_entropy"] = ent.mean().item()
    out["internal_select_acc"] = acc.mean().item()
    return out
