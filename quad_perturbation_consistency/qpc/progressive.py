"""Progressive perturbation analysis -> attention-consistency degradation curves.

Rather than one perturbation level, we sweep an escalating progression and measure how
attention consistency (same-head symmetric JS between the perturbed and original views,
aligned by token identity) degrades:

    L0 original            -- no perturbation (anchor; JS == 0 by construction).
    L1 small perturbation  -- leading positional shift only.
    L2 distractor permute  -- reorder key-value pairs and queries.
    L3 extra distractors   -- L2 + additional irrelevant filler keys.
    L4 longer context      -- L2 + many distractors + shift (long sequence).
    L5 multiple systems    -- two simultaneous relation systems (globally distinct keys so the
                              identity alignment is unambiguous), pairs permuted within.

For each level we report the mean JS, the perturbation stability (1 - JS/logC), the retrieval
stability (argmax unchanged), and the task accuracy on a matched evaluation config.  The
hypothesis predicts BD-Sync degrades more slowly than BD-A; the null predicts no advantage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

import torch
import torch.nn.functional as F

from . import _qgr_path  # noqa: F401
from qgr.mqar import MQARConfig, MQARBatch, generate_batch, split_seed, IGNORE_INDEX
from qgr.metrics import evaluate

from .perturbations import AugConfig, make_aligned_pair
from .consistency import candidate_attention, js_divergence


# (label, AugConfig for the consistency measurement, accuracy-eval MQARConfig factory key)
def _levels(fc) -> List[Dict]:
    base = dict(vocab_size=fc.vocab_size)
    return [
        {"level": 0, "label": "original",
         "aug": AugConfig(permute_pairs=False, permute_queries=False,
                          extra_distractors=0, max_pos_shift=0),
         "acc_cfg": MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 1)},
        {"level": 1, "label": "small_shift",
         "aug": AugConfig(permute_pairs=False, permute_queries=False,
                          extra_distractors=0, max_pos_shift=3),
         "acc_cfg": MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 1)},
        {"level": 2, "label": "distractor_permute",
         "aug": AugConfig(permute_pairs=True, permute_queries=True,
                          extra_distractors=0, max_pos_shift=0),
         "acc_cfg": MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 1)},
        {"level": 3, "label": "extra_distractors",
         "aug": AugConfig(permute_pairs=True, permute_queries=True,
                          extra_distractors=8, max_pos_shift=0),
         "acc_cfg": MQARConfig(fc.num_kv, fc.num_queries, 8, fc.vocab_size, 1)},
        {"level": 4, "label": "longer_context",
         "aug": AugConfig(permute_pairs=True, permute_queries=True,
                          extra_distractors=24, max_pos_shift=3),
         "acc_cfg": MQARConfig(fc.num_kv, fc.num_queries, 24, fc.vocab_size, 1)},
        # L5 handled specially (multi-system).
    ]


@torch.no_grad()
def _level_consistency(model, mq: MQARConfig, aug: AugConfig, seed: int,
                       n_batches=6, batch_size=32) -> Dict[str, float]:
    js_vals, same = [], []
    C = mq.num_kv * max(mq.n_relation_systems, 1)
    logC = math.log(max(C, 2))
    for i in range(n_batches):
        base = generate_batch(mq, split_seed(seed, "test", i), batch_size)
        pair = make_aligned_pair(base, mq, aug, seed=split_seed(seed, "test", i) + 55)
        quad_o = model(pair.tokens_o, expose_quad=True)["quad_score"]
        quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
        p_o = candidate_attention(quad_o, pair.q_idx_o, pair.k_idx_o)
        p_p = candidate_attention(quad_p, pair.q_idx_p, pair.k_idx_p)
        js = js_divergence(p_o, p_p)
        js_vals.append(float(js.mean()))
        same.append(float((p_o.argmax(-1) == p_p.argmax(-1)).float().mean()))
    mean_js = float(sum(js_vals) / len(js_vals))
    return {"mean_js": mean_js, "perturb_stability": 1.0 - mean_js / logC,
            "retrieval_stability": float(sum(same) / len(same))}


def distinct_two_system_batch(mq: MQARConfig, seed: int, batch_size: int) -> MQARBatch:
    """Two-relation-system MQAR with GLOBALLY-distinct key tokens (so identity alignment is
    unambiguous) in the standard MQAR layout: [k v ... (both systems) | queries]."""
    key_lo, key_hi, val_lo, val_hi = mq.id_ranges()
    R = 2
    total_k = mq.num_kv * R
    g = torch.Generator().manual_seed(seed)
    seqs = []
    for _ in range(batch_size):
        keys = torch.randperm(key_hi - key_lo, generator=g)[:total_k] + key_lo
        vals = torch.randperm(val_hi - val_lo, generator=g)[:total_k] + val_lo
        tokens, key_positions, val_for_kp = [], [], {}
        for j in range(total_k):
            kp = len(tokens)
            tokens.append(int(keys[j])); key_positions.append(kp)
            tokens.append(int(vals[j])); val_for_kp[kp] = int(vals[j])
        # queries: num_queries per system
        qpos, correct = [], {}
        for s in range(R):
            sys_kps = key_positions[s * mq.num_kv:(s + 1) * mq.num_kv]
            chosen = [sys_kps[int(i)] for i in
                      torch.randperm(len(sys_kps), generator=g)[:mq.num_queries]]
            for kp in chosen:
                qp = len(tokens); tokens.append(int(tokens[kp]))
                qpos.append(qp); correct[qp] = kp
        seqs.append({"tokens": tokens, "key_positions": key_positions,
                     "qpos": qpos, "correct": correct, "val_for_kp": val_for_kp})
    N = max(len(s["tokens"]) for s in seqs)
    B = batch_size
    tokens = torch.zeros(B, N, dtype=torch.long)
    targets = torch.full((B, N), IGNORE_INDEX, dtype=torch.long)
    key_pos = torch.full((B, N), -1, dtype=torch.long)
    cand = torch.zeros(B, N, N, dtype=torch.bool)
    max_q = max(len(s["qpos"]) for s in seqs)
    query_pos = torch.full((B, max_q), -1, dtype=torch.long)
    for b, s in enumerate(seqs):
        tokens[b, :len(s["tokens"])] = torch.tensor(s["tokens"])
        for j, qp in enumerate(s["qpos"]):
            kp = s["correct"][qp]
            targets[b, qp] = s["val_for_kp"][kp]
            key_pos[b, qp] = kp
            query_pos[b, j] = qp
            for ckp in s["key_positions"]:
                if ckp < qp:
                    cand[b, qp, ckp] = True
    return MQARBatch(tokens, targets, query_pos, key_pos, cand)


@torch.no_grad()
def _multisystem_consistency(model, fc, seed: int, n_batches=6, batch_size=32) -> Dict[str, float]:
    mq2 = MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 2)
    aug = AugConfig(permute_pairs=True, permute_queries=True, extra_distractors=0, max_pos_shift=0)
    js_vals, same = [], []
    C = fc.num_kv * 2
    logC = math.log(max(C, 2))
    for i in range(n_batches):
        base = distinct_two_system_batch(mq2, split_seed(seed, "test", i) + 313, batch_size)
        pair = make_aligned_pair(base, mq2, aug, seed=split_seed(seed, "test", i) + 77)
        quad_o = model(pair.tokens_o, expose_quad=True)["quad_score"]
        quad_p = model(pair.tokens_p, expose_quad=True)["quad_score"]
        p_o = candidate_attention(quad_o, pair.q_idx_o, pair.k_idx_o)
        p_p = candidate_attention(quad_p, pair.q_idx_p, pair.k_idx_p)
        js = js_divergence(p_o, p_p)
        js_vals.append(float(js.mean()))
        same.append(float((p_o.argmax(-1) == p_p.argmax(-1)).float().mean()))
    mean_js = float(sum(js_vals) / len(js_vals))
    return {"mean_js": mean_js, "perturb_stability": 1.0 - mean_js / logC,
            "retrieval_stability": float(sum(same) / len(same))}


def progressive_curve(model, fc, seed: int, n_batches=6) -> List[Dict]:
    """Full degradation curve: per-level consistency + matched-config accuracy."""
    curve = []
    for lv in _levels(fc):
        cons = _level_consistency(model, lv["acc_cfg"], lv["aug"], seed, n_batches, fc.batch_size)
        acc = evaluate(model, lv["acc_cfg"], seed, "test", n_batches, fc.batch_size)["acc"]
        curve.append({"level": lv["level"], "label": lv["label"], "accuracy": acc, **cons})
    # L5 multi-system
    mcons = _multisystem_consistency(model, fc, seed, n_batches, fc.batch_size)
    macc = evaluate(model, MQARConfig(fc.num_kv, fc.num_queries, 0, fc.vocab_size, 2),
                    seed, "test", n_batches, fc.batch_size)["acc"]
    curve.append({"level": 5, "label": "multi_system", "accuracy": macc, **mcons})
    return curve
