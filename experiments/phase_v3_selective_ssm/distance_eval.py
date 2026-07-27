"""
distance_eval.py — §10/§16.4 distance-stability + §16.5 distractor-robustness evaluation.

A variant is trained at short distances (≤256) and evaluated on longer test sequences,
since the Phase state is a streaming SSM whose state size is independent of N. Reports
Phase-state and selective-readout focus Top-1 (with shuffled/random controls) at each
distance, and at an elevated distractor rate.
"""
from __future__ import annotations

from dataclasses import replace

from .config import DataCfg
from .focus_probe import probe_all


def eval_distances(model, vocab, dcfg, distances, seed=0, n_train=600, n_eval=400):
    out = {}
    for dist in distances:
        r = probe_all(model, vocab, dcfg, dist, seed=seed, n_train=n_train, n_eval=n_eval)
        out[str(dist)] = {
            "state_top1": r["state"]["top1"],
            "selective_top1": r["selective_readout"]["top1"],
            "raw_top1": r["raw_readout"]["top1"],
            "shuffled_top1": r["shuffled_state"]["top1"],
            "random_top1": r["random_state"]["top1"],
            "state_topk": r["state"]["topk"],
            "relevance_f1": r["relevance"]["f1"],
            "relevance_auroc": r["relevance"]["auroc"],
        }
    return out


def eval_distractor_robustness(model, vocab, dcfg, distance, seed=0):
    """Increase distractor pressure: lower relevant-event rate + higher event density."""
    hard = replace(dcfg, relevant_event_rate=0.15, event_rate=0.4)
    r = probe_all(model, vocab, hard, distance, seed=seed, n_train=600, n_eval=400)
    return {"state_top1": r["state"]["top1"],
            "selective_top1": r["selective_readout"]["top1"],
            "shuffled_top1": r["shuffled_state"]["top1"],
            "relevance_f1": r["relevance"]["f1"]}
