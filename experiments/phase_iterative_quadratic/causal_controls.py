"""
causal_controls.py — §12/§14 causal controls for the iterative hybrid.

    query_frozen           : never evolve the query → iterative gain must disappear
    intermediate_shuffled  : scramble the intermediate query across examples → gain disappears
    score_shuffled         : scramble routing scores → learned routing gain disappears
    required_hop_removed    : blank a required hop's evidence tokens → answer accuracy collapses
    label_leakage          : randomize required-hop labels at eval → LEARNED arms unchanged (no leak)
    phase_zero / shuffled  : (Phase arms) zero/shuffle Phase state → Phase-specific gain disappears
"""
from __future__ import annotations

import torch

from .train import collate_iter


@torch.no_grad()
def _acc(model, data, vocab, device="cpu", **fwd):
    model.eval(); correct = total = 0
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, **fwd)
        correct += (out["answer_logits"].argmax(-1) == ans).sum().item(); total += len(b)
    return correct / max(1, total)


def _remove_required_hop(data, hop, vocab):
    out = []
    for e in data:
        e2 = dict(e); toks = list(e2["tokens"])
        if hop < len(e2["req_evidx"]):
            kp = e2["key_pos"][e2["req_evidx"][hop]]
            toks[kp] = vocab.PAD; toks[kp + 1] = vocab.PAD      # blank that evidence record
        e2["tokens"] = toks; out.append(e2)
    return out


@torch.no_grad()
def run_controls(model, data, vocab, device="cpu"):
    base = _acc(model, data, vocab, device)
    out = {"intact": base,
           "query_frozen": _acc(model, data, vocab, device, freeze_query=True),
           "intermediate_shuffled": _acc(model, data, vocab, device, shuffle_query=True),
           "score_shuffled": _acc(model, data, vocab, device, shuffle_scores=True),
           "required_hop0_removed": _acc(model, _remove_required_hop(data, 0, vocab), vocab, device),
           "required_hop1_removed": _acc(model, _remove_required_hop(data, 1, vocab), vocab, device)}
    # label-leakage: randomize required-hop positions/indices at eval; a LEARNED arm must be invariant
    lk = []
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        bad_f = reqf[torch.randperm(reqf.shape[0])]; bad_e = reqe[torch.randperm(reqe.shape[0])]
        o = model(ids, ep, pp, vl, required_hops=bad_f, req_evidx=bad_e)
        lk.append((o["answer_logits"].argmax(-1) == ans).float().mean().item())
    out["randomized_labels_at_eval"] = sum(lk) / len(lk)
    out["leakage_delta"] = abs(out["intact"] - out["randomized_labels_at_eval"])  # ~0 ⇒ no leak (learned arms)
    return out
