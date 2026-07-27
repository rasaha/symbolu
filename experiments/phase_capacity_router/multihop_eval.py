"""multihop_eval.py — §13 multi-hop admission breakdown."""
from __future__ import annotations

import statistics as st

from . import routers as R
from . import exact_store as ES


def eval_multihop(arm, model, examples, vocab, K, batch_size=32):
    recs = []
    for i in range(0, len(examples), batch_size):
        batch = examples[i:i + batch_size]
        if arm in R.MODE:
            scores = R.learned_scores(model, arm, batch, vocab)
        else:
            import torch
            g = torch.Generator().manual_seed(1)
            scores = [R.heuristic_scores(e, arm, g) for e in batch]
        for e, sc in zip(batch, scores):
            admitted = ES.admit_topk(sc, K)
            req = [j for j, ev in enumerate(e["events"]) if ev["required"]]
            n_missing = sum(1 for j in req if j not in admitted)
            g2 = ES.grade(e, admitted)
            recs.append({"missing": n_missing, "correct": g2["correct"], "n_req": len(req)})
    n = len(recs)
    p_all = sum(1 for r in recs if r["missing"] == 0) / n
    p_one = sum(1 for r in recs if r["missing"] == 1) / n
    p_two = sum(1 for r in recs if r["missing"] >= 2) / n
    acc_all = st.mean([r["correct"] for r in recs if r["missing"] == 0]) if p_all > 0 else 0.0
    return {"accuracy": st.mean([r["correct"] for r in recs]),
            "P_all_admitted": p_all, "P_one_missing": p_one, "P_two_plus_missing": p_two,
            "acc_given_all_admitted": acc_all}
