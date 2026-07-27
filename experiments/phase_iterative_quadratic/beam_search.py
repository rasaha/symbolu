"""
beam_search.py — bounded top-3 pointer beam (item 5). Eval-time decoding only; weights unchanged.

At hop 0 the structured pointer produces a distribution over candidate evidence keys. Instead of
committing to the soft mixture or the top-1, keep the TOP-3 predicted next keys, traverse each
hypothesis through the next bounded Q block (inject it as the hop-1 query), score the completed
paths, and select the best. All bounded: 3 hypotheses × one 2-hop pass each — a constant factor,
never an N×N expansion. Autonomous: uses only the predicted pointer distribution, no labels.

Four decoders compared on the SAME trained grounded_D1 model (oracle route + structured pointer):
    hard_top1  : q1 = ev[argmax pointer]
    soft       : q1 = Σ_i pointer_i ev_i          (the model's default)
    beam3      : expand top-3 pointer keys, score completed paths, pick best
    oracle_ptr : q1 = ev[req_evidx hop-1]         (upper bound; labels used ONLY here)
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .train import collate_iter


def _answer_conf(logits):
    """Path score contribution from the completed answer distribution: max log-softmax prob."""
    return F.log_softmax(logits, dim=-1).max(dim=-1).values          # [B]


@torch.no_grad()
def decode(model, data, vocab, mode="beam3", beam=3, device="cpu", batch_size=64):
    model.eval()
    correct = total = 0
    for i in range(0, len(data), batch_size):
        b = data[i:i + batch_size]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        B = len(b)

        if mode == "soft":
            pred = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["answer_logits"].argmax(-1)

        elif mode == "hard_top1":
            pred = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe,
                         hard_pointer=True)["answer_logits"].argmax(-1)

        elif mode == "oracle_ptr":
            out0 = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
            ev = out0["event_reps"]                                   # [B,Ne,D]
            nxt = reqe[:, 1].clamp(min=0) if reqe.shape[1] > 1 else torch.zeros(B, dtype=torch.long)
            q1 = ev.gather(1, nxt.view(B, 1, 1).expand(B, 1, ev.shape[-1])).squeeze(1)
            pred = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe,
                         forced_query=q1)["answer_logits"].argmax(-1)

        elif mode == "beam3":
            out0 = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
            ev = out0["event_reps"]                                   # [B,Ne,D]
            pl = out0["pointer_logits"][0]                            # [B,Ne]
            logp = F.log_softmax(pl, dim=-1)
            kk = min(beam, ev.shape[1])
            cand = pl.topk(kk, dim=-1).indices                       # [B,kk]
            best_score = torch.full((B,), -1e30, device=device)
            best_pred = torch.zeros(B, dtype=torch.long, device=device)
            for j in range(kk):
                c = cand[:, j]                                        # [B]
                q1 = ev.gather(1, c.view(B, 1, 1).expand(B, 1, ev.shape[-1])).squeeze(1)
                al = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe,
                           forced_query=q1)["answer_logits"]
                score = logp.gather(1, c.unsqueeze(1)).squeeze(1) + _answer_conf(al)   # [B]
                take = score > best_score
                best_score = torch.where(take, score, best_score)
                best_pred = torch.where(take, al.argmax(-1), best_pred)
            pred = best_pred
        else:
            raise ValueError(mode)

        correct += (pred == ans).sum().item(); total += B
    return correct / max(1, total)
