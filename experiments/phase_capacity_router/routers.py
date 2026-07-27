"""
routers.py — admission scoring for every arm (§7). Only the score differs across arms; the
exact store / capacity / grading are identical. Learned arms reuse the FROZEN-architecture
AutoGateModel (token / conditioned / cosine / bilinear matcher) over the [CUE, EVENT…] token
sequence; matcher arms use the match score, token/COND use the gate probability. Heuristic and
oracle arms need no model.
"""
from __future__ import annotations

from typing import List

import torch

from experiments.phase_v2_autonomous_gate.teacher import AutoGateModel
from . import capacity_dataset as CD

MODE = {"R-token": "token", "R-COND": "conditioned", "R-cosine": "cosine",
        "R-bilinear": "bilinear", "R-bilinear-hard": "bilinear",
        "R-shuffled": "bilinear", "R-removed": "bilinear"}


def build_router(arm, vocab, seed=0):
    torch.manual_seed(seed)
    return AutoGateModel(vocab.size, gate_mode=MODE[arm])


@torch.no_grad()
def learned_scores(model, arm, batch, vocab, device="cpu") -> List[List[float]]:
    """Per-example score at each EVENT position. Interventions for R-shuffled / R-removed."""
    ids = CD.collate(batch, vocab.PAD, device)
    mode = MODE[arm]
    override = None
    if arm == "R-shuffled":
        f = model.summary_rep(ids); override = f[torch.randperm(f.shape[0])]
    elif arm == "R-removed":
        ids2 = ids.clone(); ids2[:, 0] = vocab.PAD; ids = ids2
    if mode in ("cosine", "bilinear"):
        s = model.match_score(ids, summary_override=override)               # [B,N]
    else:
        s = torch.sigmoid(model.gate_logit(ids, summary_override=override)).mean(-1)
    out = []
    for j, e in enumerate(batch):
        out.append([s[j, p].item() for p in e["event_pos"]])
    return out


def heuristic_scores(example, kind, g=None) -> List[float]:
    events = example["events"]
    if kind == "R-random":
        return torch.rand(len(events), generator=g).tolist() if g is not None else torch.rand(len(events)).tolist()
    if kind == "R-recency":
        return [float(ev["position"]) for ev in events]
    if kind == "R-frequency":
        from collections import Counter
        c = Counter(ev["entity"] for ev in events)
        return [float(c[ev["entity"]]) for ev in events]
    if kind == "R-oracle":
        w = {"relevant": 5.0, "relevant_stale": 1.0, "hard": 1.0, "ordinary": 0.0}
        return [(10.0 if ev["required"] else w.get(ev["category"], 0.0)) for ev in events]
    if kind == "R-unlimited":
        return [1.0] * len(events)          # all admitted (K set to N by caller)
    raise ValueError(kind)
