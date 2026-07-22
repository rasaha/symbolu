"""Decode the model's per-query CLAIM and its supporting context (read-only).

In MQAR a "claim" is the model's answer to a query: the proposition *query-key k_q binds to the
predicted value v_pred*. The evidence/context is the set of key->value bindings (plus distractors)
in the sequence. Ground truth (the true value) is recorded for labelling ONLY; no feature uses it.

Per query we record: k_q, v_pred, v_true, correctness, the attention-retrieved key position and
its bound value, and compact context descriptors (key positions/tokens, value tokens, distractors)
used by the S/R/E feature modules.
"""

from __future__ import annotations

from typing import Dict, List

import torch

from . import _paths  # noqa: F401
from qgr.mqar import IGNORE_INDEX


@torch.no_grad()
def build_records(rec: Dict, batch, model) -> List[Dict]:
    """Return one record dict per query position in the batch."""
    tokens = batch.tokens
    qscore = rec["quad_score"][rec["num_layers"] - 1].mean(dim=1)   # [B,N,N] head-mean Quad score
    pred = rec["pred"]                                              # [B,N]
    B, N = tokens.shape
    records: List[Dict] = []
    for b in range(B):
        # context: key positions (candidates), their tokens and bound values, distractors
        key_positions = torch.nonzero(batch.cand_mask[b].any(0), as_tuple=False).flatten().tolist()
        key_positions = sorted(key_positions)
        key_tokens = [int(tokens[b, kp]) for kp in key_positions]
        value_tokens = [int(tokens[b, kp + 1]) for kp in key_positions]
        val_for_keypos = {kp: int(tokens[b, kp + 1]) for kp in key_positions}
        key_token_set = set(key_tokens)
        value_token_set = set(value_tokens)
        # all non-pad tokens before the query region that are not part of a k/v pair == distractors
        qmask_row = batch.key_pos[b] >= 0
        for q in torch.nonzero(qmask_row, as_tuple=False).flatten().tolist():
            k_q = int(tokens[b, q])
            v_pred = int(pred[b, q])
            v_true = int(batch.targets[b, q])
            # attention-retrieved key among candidates strictly before q
            cand = batch.cand_mask[b, q]
            row = qscore[b, q].masked_fill(~cand, float("-inf"))
            retrieved_kp = int(row.argmax())
            v_retrieved = val_for_keypos.get(retrieved_kp, -1)
            # context key positions equal to the query key token (for evidence adjacency)
            kq_keypositions = [kp for kp in key_positions if int(tokens[b, kp]) == k_q]
            records.append({
                "b": b, "q": q, "k_q": k_q, "v_pred": v_pred, "v_true": v_true,
                "correct": int(v_pred == v_true), "failure": int(v_pred != v_true),
                "retrieved_kp": retrieved_kp, "v_retrieved": v_retrieved,
                "key_positions": key_positions, "key_tokens": key_tokens,
                "value_tokens": value_tokens, "val_for_keypos": val_for_keypos,
                "kq_keypositions": kq_keypositions,
                "num_candidates": int(cand.sum()),
                "key_token_set": key_token_set, "value_token_set": value_token_set,
            })
    return records
