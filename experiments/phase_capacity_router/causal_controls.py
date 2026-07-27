"""
causal_controls.py — §14 causal routing controls + causal_delta.

The claimed router gain (if any) must depend on the focus summary and on meaningful scores.
Runs the trained matcher under interventions and reports the delta from the intact router.
"""
from __future__ import annotations

import torch

from . import routers as R
from . import exact_store as ES


@torch.no_grad()
def _admit_eval(model, arm, examples, vocab, K, score_transform=None, batch_size=32):
    correct = 0
    for i in range(0, len(examples), batch_size):
        batch = examples[i:i + batch_size]
        scores = R.learned_scores(model, arm, batch, vocab)
        for e, sc in zip(batch, scores):
            if score_transform:
                sc = score_transform(sc)
            correct += ES.grade(e, ES.admit_topk(sc, K))["correct"]
    return correct / max(1, len(examples))


@torch.no_grad()
def run_controls(model, base_arm, examples, vocab, K):
    """base_arm is a matcher arm (e.g. R-bilinear-hard). Returns intact + intervention accuracies."""
    g = torch.Generator().manual_seed(0)
    out = {"intact": _admit_eval(model, base_arm, examples, vocab, K)}
    out["summary_removed"] = _admit_eval(model, "R-removed", examples, vocab, K)
    out["summary_shuffled"] = _admit_eval(model, "R-shuffled", examples, vocab, K)
    # matcher score shuffled across events within each example (destroys ranking signal)
    def shuffle_scores(sc):
        idx = torch.randperm(len(sc), generator=g).tolist()
        return [sc[j] for j in idx]
    out["score_shuffled"] = _admit_eval(model, base_arm, examples, vocab, K, score_transform=shuffle_scores)
    out["causal_delta"] = out["intact"] - max(out["summary_removed"], out["summary_shuffled"], out["score_shuffled"])
    return out
