"""hop_diagnostics.py — §8/§11 per-hop routing diagnostics."""
from __future__ import annotations

import statistics as st
import torch

from .train import collate_iter


@torch.no_grad()
def diagnose(model, data, vocab, device="cpu"):
    model.eval()
    q_norms, rank_by_hop, incl_by_hop = [], {}, {}
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
        q_norms.append(out.get("query_update_norms"))
        for h, sc in enumerate(out["route_scores"]):
            order = sc.argsort(dim=-1, descending=True)              # [B,Ne]
            tgt = reqe[:, h] if h < reqe.shape[1] else torch.full((sc.shape[0],), -1, device=device)
            valid = tgt >= 0
            if valid.any():
                rank = (order == tgt.unsqueeze(1)).float().argmax(-1)      # required-event rank
                K = min(model.K, sc.shape[1]) if model.K else 0
                incl = (rank < K) if K else torch.zeros_like(rank, dtype=torch.bool)
                rank_by_hop.setdefault(h, []).extend(rank[valid].tolist())
                incl_by_hop.setdefault(h, []).extend(incl[valid].float().tolist())
    qn = [x for x in q_norms if x]
    mean_qnorm = [st.mean([q[h] for q in qn]) for h in range(len(qn[0]))] if qn else []
    return {
        "query_update_norm_by_hop": mean_qnorm,
        "required_rank_by_hop": {h: st.mean(v) for h, v in rank_by_hop.items()},
        "required_topk_inclusion_by_hop": {h: st.mean(v) for h, v in incl_by_hop.items()},
    }
