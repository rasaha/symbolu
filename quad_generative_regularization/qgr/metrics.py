"""Evaluation metrics for MQAR."""

from __future__ import annotations

from typing import Dict

import torch

from .mqar import IGNORE_INDEX, MQARConfig, iter_batches
from .losses import task_loss, mechanism_diagnostics


@torch.no_grad()
def evaluate(model, mqar_cfg: MQARConfig, base_seed: int, split: str,
             n_batches: int, batch_size: int, device="cpu") -> Dict[str, float]:
    """Return exact-match accuracy (per query), sequence-level accuracy, and task loss."""
    model.eval()
    correct = 0
    total = 0
    seq_correct = 0
    seq_total = 0
    loss_sum = 0.0
    loss_batches = 0
    for batch in iter_batches(mqar_cfg, base_seed, split, n_batches, batch_size, device):
        out = model(batch.tokens)
        logits = out["logits"]
        preds = logits.argmax(dim=-1)                 # [B,N]
        qmask = batch.targets != IGNORE_INDEX         # [B,N]
        hit = (preds == batch.targets) & qmask
        correct += int(hit.sum())
        total += int(qmask.sum())
        # sequence-level exact match: all queries in a sequence correct
        per_seq_q = qmask.sum(dim=1)
        per_seq_hit = hit.sum(dim=1)
        seq_correct += int((per_seq_hit == per_seq_q).sum())
        seq_total += batch.tokens.shape[0]
        loss_sum += float(task_loss(logits, batch.targets))
        loss_batches += 1
    return {
        "acc": correct / max(total, 1),
        "seq_acc": seq_correct / max(seq_total, 1),
        "task_loss": loss_sum / max(loss_batches, 1),
        "n_queries": total,
    }


@torch.no_grad()
def quad_mechanism(model, mqar_cfg: MQARConfig, base_seed: int, split: str,
                   n_batches: int, batch_size: int, device="cpu") -> Dict[str, float]:
    """Aggregate Quad-score mechanism diagnostics over a split."""
    model.eval()
    agg: Dict[str, float] = {}
    count = 0
    for batch in iter_batches(mqar_cfg, base_seed, split, n_batches, batch_size, device):
        out = model(batch.tokens, expose_quad=True)
        diag = mechanism_diagnostics(out["quad_score"], batch.key_pos, batch.cand_mask)
        for k, v in diag.items():
            if v == v:  # not NaN
                agg[k] = agg.get(k, 0.0) + v
        count += 1
    return {k: v / max(count, 1) for k, v in agg.items()}
