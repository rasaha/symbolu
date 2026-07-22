"""Build the per-query feature dataset across model seeds and conditions (read-only).

The model is the frozen bounded task-only Quad transformer (BD-A), trained once per seed by the
unmodified prior package and frozen. For every query we assemble: the correctness label, the SCC
features (S, R, E, T), and the baselines (A confidence, B entailment, C grounding). Ground truth
forms the label only.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch

from . import _paths  # noqa: F401
from qgr.mqar import generate_batch, split_seed
from use.capture import run_inference
from use.dataset import bounded_fc, train_model, conditions

from . import claims, features_S, features_R, features_E, features_T, baselines


@torch.no_grad()
def build_condition(model, mq, seed: int, cond_idx: int, n_batches: int, batch_size: int,
                    M: int = 4) -> Dict[str, np.ndarray]:
    acc: Dict[str, List[np.ndarray]] = {}
    labels, correct = [], []
    for i in range(n_batches):
        base = generate_batch(mq, split_seed(seed, "test", 20_000 + cond_idx * 1000 + i), batch_size)
        rec = run_inference(model, base.tokens)
        records = claims.build_records(rec, base, model)
        if not records:
            continue
        labels.append(np.array([r["failure"] for r in records]))
        correct.append(np.array([r["correct"] for r in records]))
        groups = {
            **{f"S::{k}": v for k, v in features_S.compute(records, rec, model).items()},
            **{f"R::{k}": v for k, v in features_R.compute(records, rec, model).items()},
            **{f"E::{k}": v for k, v in features_E.compute(records, rec, model).items()},
            **{f"T::{k}": v for k, v in features_T.compute(records, base, mq, model, seed,
                                                           cond_idx, M=M).items()},
            **baselines.confidence(rec, records),
            **baselines.entailment(records, rec, model),
            **baselines.grounding(records, rec, model),
        }
        for k, v in groups.items():
            acc.setdefault(k, []).append(v)
    out = {k: np.concatenate(v) for k, v in acc.items()}
    out["label_failure"] = np.concatenate(labels) if labels else np.zeros(0, int)
    out["correct"] = np.concatenate(correct) if correct else np.zeros(0, int)
    return out


def build_all(seeds: List[int], n_batches: int = 30, batch_size: int = 32, M: int = 4,
              alpha: float = 4.0, verbose=True) -> Dict:
    fc = bounded_fc(alpha)
    conds = conditions(fc)
    data, model_acc = {}, {}
    for s in seeds:
        model, acc = train_model(fc, s)
        model_acc[s] = acc
        if verbose:
            print(f"[seed {s}] BD-A in-dist acc={acc:.3f}")
        data[s] = {}
        for ci, (cname, mq) in enumerate(conds.items()):
            d = build_condition(model, mq, s, ci, n_batches, batch_size, M=M)
            data[s][cname] = d
            if verbose:
                n = len(d["label_failure"]); fr = float(d["label_failure"].mean()) if n else float("nan")
                tcov = float(np.mean(~np.isnan(d.get("T::T_flip_rate", np.array([np.nan]))))) \
                    if "T::T_flip_rate" in d else 0.0
                print(f"  {cname:18s}: queries={n} failure_rate={fr:.3f} T_coverage={tcov:.2f}")
    return {"data": data, "model_acc": model_acc, "seeds": seeds,
            "conditions": list(conds.keys()), "n_batches": n_batches,
            "batch_size": batch_size, "M": M, "alpha": alpha}
