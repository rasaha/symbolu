"""capacity_sweep.py — §12 accuracy/admission as functions of K, N, N/K pressure."""
from __future__ import annotations

from .config import LADDER
from .capacity_dataset import generate
from .evaluate import evaluate_arm


def sweep(arm, model, vocab, dcfg, seed, ladder=LADDER, n=200):
    out = {}
    for N, Ks in ladder:
        for K in Ks:
            te = generate(vocab, dcfg, N, K, n, 9000 + seed)
            r = evaluate_arm(arm, model, te, vocab, K)
            out[f"N{N}_K{K}"] = {"N": N, "K": K, "ratio": N / K,
                                 "accuracy": r["accuracy"], "relevant_recall": r["relevant_recall"],
                                 "hard_false_admit": r["hard_false_admit"]}
    return out
