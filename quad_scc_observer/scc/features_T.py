"""Hypothesis T — inference stability under semantically-equivalent perturbations (read-only).

Reuses the perturbation-consistency machinery to generate M semantically-equivalent views of each
sequence (pair/query reorder, extra irrelevant distractors, positional shift) that preserve every
binding and answer. For each query we measure how stable the model's PREDICTION is across views:

  T_flip_rate   : fraction of views whose argmax answer differs from the original      (higher=less stable)
  T_prob_mean   : mean probability the model assigns to its ORIGINAL predicted value across views
  T_prob_std    : std of that probability across views
  T_answer_entropy : entropy over the distribution of distinct predicted answers across views

Observer only: no retraining, no regularization; the model runs its ordinary forward pass on each
view. Queries not covered by a view's alignment (rare token collisions in multi-system contexts)
are left as NaN and reported as coverage.
"""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np
import torch

from . import _paths  # noqa: F401
from qpc.perturbations import make_aligned_pair, AugConfig
from qgr.mqar import split_seed

FEATURES = ["T_flip_rate", "T_prob_mean", "T_prob_std", "T_answer_entropy"]


@torch.no_grad()
def compute(records: List[Dict], base_batch, mq, model, base_seed: int, cond_idx: int,
            M: int = 4, aug: AugConfig = None) -> Dict[str, np.ndarray]:
    if aug is None:
        aug = AugConfig(permute_pairs=True, permute_queries=True, extra_distractors=4,
                        max_pos_shift=3)
    P = len(records)
    # index records by (batch row, query-token identity); the perturbed view is aligned by TOKEN,
    # not by position, because make_aligned_pair rebuilds view O canonically (positions differ when
    # the base has distractors). Query tokens are distinct within a single-relation sample.
    rec_index = {(r["b"], r["k_q"]): i for i, r in enumerate(records)}
    v_pred = np.array([r["v_pred"] for r in records])
    agree = [[] for _ in range(P)]
    probs_on_pred = [[] for _ in range(P)]
    answers = [[] for _ in range(P)]

    for m in range(M):
        seed = split_seed(base_seed, "test", 40_000 + cond_idx * 100 + m) + 7 * m + 1
        try:
            pair = make_aligned_pair(base_batch, mq, aug, seed=seed)
        except Exception:
            continue
        out = model(pair.tokens_p)
        logits = out["logits"]
        pprob = torch.softmax(logits, dim=-1)
        ppred = logits.argmax(-1)
        B, Qc = pair.q_idx_p.shape
        for b in range(B):
            for j in range(Qc):
                pp = int(pair.q_idx_p[b, j])
                tok = int(pair.tokens_p[b, pp])          # query token at this perturbed position
                key = (b, tok)
                if key not in rec_index:
                    continue
                i = rec_index[key]
                a = int(ppred[b, pp])
                answers[i].append(a)
                agree[i].append(1 if a == v_pred[i] else 0)
                probs_on_pred[i].append(float(pprob[b, pp, v_pred[i]]))

    flip = np.full(P, np.nan); pm = np.full(P, np.nan)
    ps = np.full(P, np.nan); ent = np.full(P, np.nan)
    for i in range(P):
        if not agree[i]:
            continue
        flip[i] = 1.0 - float(np.mean(agree[i]))
        pm[i] = float(np.mean(probs_on_pred[i]))
        ps[i] = float(np.std(probs_on_pred[i]))
        vals, counts = np.unique(answers[i], return_counts=True)
        p = counts / counts.sum()
        ent[i] = float(-(p * np.log(p + 1e-12)).sum())
    return {"T_flip_rate": flip, "T_prob_mean": pm, "T_prob_std": ps, "T_answer_entropy": ent}
