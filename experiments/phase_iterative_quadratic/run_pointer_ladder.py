"""
run_pointer_ladder.py — structured soft-pointer query-update repair (autonomous).

Query update replaced by a structured soft pointer over the CANDIDATE EVIDENCE KEYS:
    scores_i = (W_ptr o)·ev_i ;  pointer = softmax(scores) ;  q_next = Σ_i pointer_i ev_i
Training may supervise the correct next evidence event (req_evidx[:,h+1]); autonomous evaluation
uses ONLY the predicted pointer distribution — no ground-truth intermediate query / event id / path.

Reports (per arm):
  D0 (oracle route + GT query), grounded-D1 (oracle route + pointer query),
  grounded-D2 (learned route + pointer query); next-entity top-1 / top-K; correct-entity
  probability; pointer entropy; final accuracy conditioned on a correct pointer;
  hard-argmax-pointer ablation.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import torch

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg
from .hybrid_model import IterativeHybrid
from .train import train_hybrid, collate_iter
from .evaluate import evaluate

HERE = Path(__file__).resolve().parent


@torch.no_grad()
def pointer_metrics(model, data, vocab, K=3, hard_pointer=False, device="cpu"):
    """Autonomous next-entity pointer metrics + accuracy-conditioned-on-correct-pointer."""
    model.eval()
    top1 = topk = corr_prob = ent = n_ptr = 0.0
    acc_all = acc_cp = n_cp = n_all = 0
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, hard_pointer=hard_pointer)
        pred = out["answer_logits"].argmax(-1)
        acc_all += (pred == ans).sum().item(); n_all += len(b)
        # pointer after hop 0 should select the hop-1 required event (the next entity/evidence).
        pls = out["pointer_logits"]
        if not pls:
            continue
        pl = pls[0]                                    # [B, Ne]
        tgt = reqe[:, 1] if reqe.shape[1] > 1 else torch.full((len(b),), -1)
        valid = tgt >= 0
        if valid.any():
            p = torch.softmax(pl[valid], dim=-1)       # [b, Ne]
            t = tgt[valid]
            top1 += (p.argmax(-1) == t).sum().item()
            kk = min(K, p.shape[1])
            topk += (p.topk(kk, dim=-1).indices == t.unsqueeze(1)).any(-1).sum().item()
            corr_prob += p.gather(1, t.unsqueeze(1)).squeeze(1).sum().item()
            ent += (-(p.clamp_min(1e-9).log() * p).sum(-1)).sum().item()
            n_ptr += valid.sum().item()
            # accuracy conditioned on a correct top-1 pointer
            cp = (p.argmax(-1) == t)
            idx = valid.nonzero(as_tuple=True)[0]
            acc_cp += ((pred[idx] == ans[idx]) & cp).sum().item()
            n_cp += cp.sum().item()
    return {
        "final_accuracy": acc_all / max(1, n_all),
        "next_entity_top1": top1 / max(1, n_ptr),
        "next_entity_topk": topk / max(1, n_ptr),
        "correct_entity_prob": corr_prob / max(1, n_ptr),
        "pointer_entropy": ent / max(1, n_ptr),
        "acc_given_correct_pointer": acc_cp / max(1, n_cp),
        "n_pointer": int(n_ptr),
    }


def _train(vocab, nid, gen, steps, **kw):
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, **kw)
    train_hybrid(m, gen, vocab, TrainCfg(seed=0, steps=steps))
    return m


def run(N=32, steps=3000):
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time()
    g2 = lambda bs, s: generate(vocab, N, 2, bs, s)
    te2 = generate(vocab, N, 2, 300, 77000)
    res = {}

    arms = [
        ("D0", dict(hops=2, routing_mode="oracle", gt_query=True, W=N, K=8)),
        ("grounded_D1", dict(hops=2, routing_mode="oracle", pointer_query=True, W=N, K=8)),
        ("grounded_D2", dict(hops=2, routing_mode="learned", router_kind="cond",
                             pointer_query=True, W=N, K=8)),
    ]
    for name, kw in arms:
        m = _train(vocab, nid, g2, steps, **kw)
        acc = evaluate(m, te2, vocab)["accuracy"]
        entry = {"accuracy": acc}
        if kw.get("pointer_query"):
            entry.update(pointer_metrics(m, te2, vocab))
            entry["hard_pointer"] = pointer_metrics(m, te2, vocab, hard_pointer=True)
        res[name] = entry
        print(f"{name}: acc={acc:.3f} ({time.time()-t0:.0f}s)  {json.dumps(entry, default=float)}",
              flush=True)

    res["gate"] = {
        "D0_ge_0.95": res["D0"]["accuracy"] >= 0.95,
        "grounded_D1_ge_0.85": res["grounded_D1"]["accuracy"] >= 0.85,
        "grounded_D2": res["grounded_D2"]["accuracy"],
        "verdict": ("grounded_D1_passes" if res["grounded_D1"]["accuracy"] >= 0.85 else
                    "query_update_still_bottleneck"),
    }
    (HERE / "results" / "pointer_ladder.json").write_text(json.dumps(res, indent=2, default=float))
    print("POINTER_LADDER:", json.dumps(res["gate"], indent=1, default=float), flush=True)
    print("POINTER_LADDER DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
