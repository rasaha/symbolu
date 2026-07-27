"""evaluate.py — answer accuracy + per-hop retrieval + complete-chain (§11)."""
from __future__ import annotations

import torch

from .train import collate_iter


@torch.no_grad()
def evaluate(model, data, vocab, device="cpu", batch_size=64):
    model.eval()
    correct = total = 0
    hop_hit = {}; chain_hit = 0; n_chain = 0
    for i in range(0, len(data), batch_size):
        b = data[i:i + batch_size]
        ids, ep, pp, vl, ans, reqf, reqe, hoptgt = collate_iter(b, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf)
        pred = out["answer_logits"].argmax(-1)
        correct += (pred == ans).sum().item(); total += len(b)
        # per-hop admission: was the required hop-h event in the routed top-K at hop h?
        for h, sc in enumerate(out["route_scores"]):
            K = min(model.K, sc.shape[1]) if model.K > 0 else 0
            if K == 0:
                continue
            topk = sc.topk(K, dim=-1).indices
            tgt = reqe[:, h] if h < reqe.shape[1] else torch.full((sc.shape[0],), -1, device=device)
            valid = tgt >= 0
            hit = ((topk == tgt.unsqueeze(1)).any(-1) & valid)
            hop_hit.setdefault(h, [0, 0])
            hop_hit[h][0] += hit.sum().item(); hop_hit[h][1] += valid.sum().item()
        # complete-chain: all required hops admitted
        allhit = torch.ones(len(b), dtype=torch.bool, device=device)
        for h, sc in enumerate(out["route_scores"]):
            if model.K == 0:
                continue
            topk = sc.topk(min(model.K, sc.shape[1]), dim=-1).indices
            tgt = reqe[:, h] if h < reqe.shape[1] else torch.full((sc.shape[0],), -1, device=device)
            allhit &= ((topk == tgt.unsqueeze(1)).any(-1) | (tgt < 0))
        chain_hit += allhit.sum().item(); n_chain += len(b)
    return {"accuracy": correct / max(1, total),
            "hop_recall": {h: (v[0] / max(1, v[1])) for h, v in hop_hit.items()},
            "complete_chain_retrieval": chain_hit / max(1, n_chain),
            "n": total}
