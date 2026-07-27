"""
evaluate.py — score → admit top-K → exact store → grade, for any router arm.

Identical exact store / capacity / grading across arms; only the score differs. Uses the
streaming bounded top-K buffer (O(K) state) and verifies it matches full-ranking admission.
Aggregates admission recall/precision, hard-negative false-admission, exact answer accuracy,
all-required-admitted rate, oracle-gap closure, and capacity utilization.
"""
from __future__ import annotations

import statistics as st
from typing import List

import torch

from . import routers as R
from . import exact_store as ES
from .admission_buffer import stream_admit


def _scores_for(arm, model, batch, vocab):
    if arm in R.MODE:
        return R.learned_scores(model, arm, batch, vocab)
    g = torch.Generator().manual_seed(12345)
    return [R.heuristic_scores(e, arm, g) for e in batch]


def evaluate_arm(arm, model, examples, vocab, K, batch_size=32):
    recs = []
    for i in range(0, len(examples), batch_size):
        batch = examples[i:i + batch_size]
        scores = _scores_for(arm, model, batch, vocab)
        for e, sc in zip(batch, scores):
            k_eff = e["N"] if arm == "R-unlimited" else K
            admitted = ES.admit_topk(sc, k_eff)
            # streaming-equivalence check (bounded O(K)); admitted set must match
            stream_set, repl = stream_admit(sc, k_eff)
            g = ES.grade(e, admitted)
            g["replacements"] = repl
            g["stream_matches_full"] = int(stream_set == admitted)
            recs.append(g)
    agg = {}
    keys = ["correct", "all_required_admitted", "relevant_recall", "relevant_precision",
            "hard_false_admit", "ordinary_false_admit", "topk_purity", "capacity_util",
            "replacements", "stream_matches_full"]
    for k in keys:
        agg[k] = st.mean([r[k] for r in recs])
    agg["accuracy"] = agg["correct"]
    agg["n"] = len(recs)
    return agg
