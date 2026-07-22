"""Standard confidence baselines computed per query (read-only, no ground truth).

USE must beat these to have value. All are oriented so that HIGHER = more confident (i.e. lower
predicted failure probability); the failure-detection orientation is handled in evaluation.

  token_prob      max softmax probability of the predicted answer token
  logprob         log of token_prob
  neg_entropy     - Shannon entropy of the output distribution  (higher = more peaked)
  margin          top1 - top2 output probability
  seq_confidence  mean token_prob over all query positions in the same sequence
  attn_neg_entropy - mean (over heads) entropy of the Quad attention distribution at the query
  random          a fixed random score (chance-level control)
"""

from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn.functional as F

BASELINE_NAMES = ["token_prob", "logprob", "neg_entropy", "margin",
                  "seq_confidence", "attn_neg_entropy", "random"]


@torch.no_grad()
def baseline_signals(rec: Dict, query_bq: Tuple[torch.Tensor, torch.Tensor],
                     rng_seed: int = 0) -> Dict[str, torch.Tensor]:
    b_idx, q_idx = query_bq
    probs = rec["probs"]                              # [B,N,V]
    logits = rec["logits"]
    Q = b_idx.shape[0]
    p = probs[b_idx, q_idx]                           # [Q,V]
    top2 = p.topk(2, dim=-1).values                   # [Q,2]
    token_prob = top2[:, 0]
    margin = top2[:, 0] - top2[:, 1]
    ent = -(p.clamp_min(1e-12) * p.clamp_min(1e-12).log()).sum(-1)   # [Q]
    logprob = token_prob.clamp_min(1e-12).log()

    # sequence confidence: mean token_prob across queries sharing the same batch row
    seq_conf = torch.zeros(Q)
    B = probs.shape[0]
    sums = torch.zeros(B); cnts = torch.zeros(B)
    sums.index_add_(0, b_idx, token_prob)
    cnts.index_add_(0, b_idx, torch.ones(Q))
    seq_mean = sums / cnts.clamp_min(1)
    seq_conf = seq_mean[b_idx]

    # attention entropy at the query (mean over heads), over causally-valid positions
    qscore = rec["quad_score"][rec["num_layers"] - 1]     # [B,H,N,N] last (aux) layer
    rows = qscore[b_idx, :, q_idx]                        # [Q,H,N]
    attn = F.softmax(rows, dim=-1)                        # over valid (future = -inf -> 0)
    a_ent = -(attn.clamp_min(1e-12) * attn.clamp_min(1e-12).log()).sum(-1).mean(-1)  # [Q]

    g = torch.Generator().manual_seed(rng_seed)
    rand = torch.rand(Q, generator=g)
    return {
        "token_prob": token_prob, "logprob": logprob, "neg_entropy": -ent,
        "margin": margin, "seq_confidence": seq_conf, "attn_neg_entropy": -a_ent,
        "random": rand,
    }
