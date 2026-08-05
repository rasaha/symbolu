#!/usr/bin/env python3
"""Extended evaluator for the three-factor factorial. Reuses the frozen temporal task + cohort. Per split
it reports the full null-inclusive decision partition plus the inherited null-excluded addressing metric.

Metric conventions:
  * pred_all  = argmax over the K real candidates + null  (index K = abstain)  -> full decision.
  * pred_key  = argmax over the K real candidates only     (inherited null-excluded addressing).
  * T4 accuracy (gated)      = correct_latest = P(pred_all == target index)  [null-inclusive].
  * addressing_top1 (inherited, gated for T1/T2/T3/T6/T7/T9) = P(pred_key == target index).
  * Partition of pred_all on valid queries: correct_latest | null | wrong_entity | right_entity_wrong_older.
  * correct_entity = correct_latest + right_entity_wrong_older.
  * e2e = value correct (abstain counts as wrong); with the clean value path this tracks correct_latest.
  * false_reject = abstain rate on valid queries; false_accept = accept rate on T8 no-match.
No evaluator ground-truth is fed to the model; targets are used ONLY to score predictions after the fact.
"""
from __future__ import annotations

import pathlib
import sys

import torch

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
if str(TEMPORAL_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPORAL_DIR))
import temporal_task as T             # noqa: E402
from temporal_train import collate    # noqa: E402

import factor_config as C             # noqa: E402


def _entity(kt_row):
    return tuple(sorted(((kt_row[0] - T._E) // T.SYN, (kt_row[1] - T._E) // T.SYN)))


def build_cohort(seed):
    """Fresh reserved cohort for one seed; identical across all cells."""
    return T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], C.EVAL_N_PER_SPLIT, seed_base=seed)


@torch.no_grad()
def eval_split(model, eps, tau):
    model.eval()
    kt, qt, kv, ti, tv = collate(eps)
    K = kt.size(1)
    scores = model.scores(kt, qt, tau)             # [B,K+1]
    key_scores = scores[:, :K]
    pred_all = scores.argmax(-1)
    pred_key = key_scores.argmax(-1)
    valid = ti >= 0
    out = {"n": len(eps)}
    if valid.any():
        vi = ti[valid]
        pa = pred_all[valid]
        pk = pred_key[valid]
        ktv = kt[valid]
        n = int(valid.sum())
        abst = (pa == K)
        # per-query entity comparison (python loop over the valid rows; 150 max)
        same_entity = torch.zeros(n, dtype=torch.bool)
        for r in range(n):
            if not abst[r]:
                same_entity[r] = (_entity(ktv[r, pa[r]].tolist()) == _entity(ktv[r, vi[r]].tolist()))
        correct_latest = (pa == vi)
        right_older = (~abst) & same_entity & (~correct_latest)
        wrong_entity = (~abst) & (~same_entity)
        chosen = kv[valid].gather(1, pa.clamp(max=K - 1).view(-1, 1)).squeeze(1)
        cs = key_scores[valid].gather(1, vi.view(-1, 1)).squeeze(1)
        out.update({
            "addressing_top1": float((pk == vi).float().mean()),             # inherited null-excluded
            "correct_latest": float(correct_latest.float().mean()),          # null-inclusive T4 accuracy
            "correct_latest_record": float(correct_latest.float().mean()),
            "correct_entity": float(((correct_latest) | right_older).float().mean()),
            "null_rate": float(abst.float().mean()),
            "wrong_entity": float(wrong_entity.float().mean()),
            "right_entity_wrong_older": float(right_older.float().mean()),
            "e2e": float(((~abst) & (chosen == tv[valid])).float().mean()),
            "false_reject": float(abst.float().mean()),
            "mean_correct_key_rank": float(((key_scores[valid] > cs.view(-1, 1)).sum(1) + 1).float().mean()),
        })
    if (~valid).any():
        pa = pred_all[~valid]
        out["false_accept"] = float((pa != K).float().mean())
    return out


def eval_cell(model, cohort, tau=C.TAU):
    return {name: eval_split(model, eps, tau) for name, eps in cohort.items()}
