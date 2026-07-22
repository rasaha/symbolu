"""Hypothesis S — semantic similarity features (read-only, representation-based).

Cosine similarity is treated as a FEATURE, not as semantic truth. These measure agreement between
the model's claim and its context in embedding/representation space:

  S_qk_retrieved_cos : cos(projected query, projected retrieved key)  -- retrieval match strength
  S_hq_vpred_cos     : cos(final query hidden state, predicted-value embedding)
  S_vpred_vretr_cos  : cos(predicted-value emb, attention-retrieved-value emb) -- pred/attn agreement
  S_hq_ctxval_cos    : cos(final query hidden state, mean context-value embedding)

All are computed from frozen states; none use the ground-truth label.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch
import torch.nn.functional as F

from . import _paths  # noqa: F401

FEATURES = ["S_qk_retrieved_cos", "S_hq_vpred_cos", "S_vpred_vretr_cos", "S_hq_ctxval_cos"]


@torch.no_grad()
def compute(records: List[Dict], rec: Dict, model) -> Dict[str, np.ndarray]:
    L = rec["num_layers"] - 1
    attn = model.blocks[L].attn
    h_in = rec["block_in"][L]
    qproj = attn.W_q(attn.norm_q(h_in))        # [B,N,D]
    kproj = attn.W_k(attn.norm_m(h_in))        # [B,N,D]
    h_out = rec["block_out"][L]                # [B,N,D] final residual (query state)
    emb = model.token_emb.weight               # [V,D]

    b = torch.tensor([r["b"] for r in records])
    q = torch.tensor([r["q"] for r in records])
    rk = torch.tensor([r["retrieved_kp"] for r in records])
    vpred = torch.tensor([r["v_pred"] for r in records])
    vretr = torch.tensor([max(r["v_retrieved"], 0) for r in records])
    vretr_valid = torch.tensor([1.0 if r["v_retrieved"] >= 0 else 0.0 for r in records])

    qv = qproj[b, q]                           # [P,D]
    kv = kproj[b, rk]                           # [P,D]
    hq = h_out[b, q]                            # [P,D]
    e_vpred = emb[vpred]                        # [P,D]
    e_vretr = emb[vretr]                        # [P,D]

    # mean context-value embedding per query
    ctx_means = []
    for r in records:
        vt = r["value_tokens"]
        ctx_means.append(emb[torch.tensor(vt)].mean(0) if vt else torch.zeros(emb.shape[1]))
    ctx_mean = torch.stack(ctx_means)          # [P,D]

    out = {
        "S_qk_retrieved_cos": F.cosine_similarity(qv, kv, dim=-1),
        "S_hq_vpred_cos": F.cosine_similarity(hq, e_vpred, dim=-1),
        "S_vpred_vretr_cos": F.cosine_similarity(e_vpred, e_vretr, dim=-1) * vretr_valid,
        "S_hq_ctxval_cos": F.cosine_similarity(hq, ctx_mean, dim=-1),
    }
    return {k: v.numpy() for k, v in out.items()}
