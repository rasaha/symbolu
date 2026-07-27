"""
serializer.py — structured evidence-chain output (§12), production-compatible contract.

Turns a model run on one example into an auditable packet the external LLM would consume:
answer candidate, selected evidence IDs, and the per-hop evidence chain (each hop referring
back to an exact evidence record by ID). The model RANKS and CONNECTS evidence; it never
rewrites source records. A failure_reason is emitted when the chain is incomplete. Outputs
refer to evidence IDs / source positions — never to a latent vector or a bare class index.
"""
from __future__ import annotations

from typing import Dict

import torch

from .train import collate_iter


@torch.no_grad()
def serialize(model, example, vocab, K=None) -> Dict:
    model.eval()
    ids, ep, pp, vl, ans, reqf, reqe, hoptgt = collate_iter([example], vocab)
    out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
    K = K or model.K or 1
    events = example["events"]
    chain, selected_ids = [], []
    complete = True
    for h, sc in enumerate(out["route_scores"]):
        order = sc[0].argsort(descending=True).tolist()
        top = order[:max(1, K)]
        # the chain link this hop is meant to recover
        needed = example["req_evidx"][h] if h < len(example["req_evidx"]) else None
        admitted = needed is not None and needed in top
        rank = (order.index(needed) if needed is not None else -1)
        pick = needed if (needed is not None and admitted) else top[0]
        ev = events[pick]
        chain.append({"hop": h, "evidence_id": ev["evidence_id"], "source_ref": ev["source_pos"],
                      "entity": ev["entity"], "relation": ev["relation"], "value": ev["value"],
                      "required_admitted": bool(admitted), "required_rank": int(rank)})
        selected_ids.append(ev["evidence_id"])
        if needed is not None and not admitted:
            complete = False
    pred = int(out["answer_logits"].argmax(-1).item())
    return {
        "query": {"focus_entity": example["focus"][0], "focus_relation": example["focus"][1]},
        "answer_candidate": pred,
        "answer_correct": bool(pred == example["answer"]),
        "selected_evidence_ids": selected_ids,
        "evidence_chain": chain,
        "hop_order": list(range(len(chain))),
        "confidence": float(out["answer_logits"].softmax(-1).max().item()),
        "chain_complete": complete,
        "failure_reason": None if complete else "required evidence not admitted at one or more hops",
    }
