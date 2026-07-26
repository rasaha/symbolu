"""
ablations.py — §7/§13 coefficient and role ablations for the Phase-v2 retention signal.

lambda_sweep: train D-v2 at fixed λ ∈ {0, 0.01, 0.05, 0.10, 0.25} and report target
survival — confirming Phase must not dominate eviction (small λ) yet a nonzero λ helps.
The arm ablations (D-zero ≈ C, D-random/shuffled ≤ C, D-v1 ≤ D-v2) are the primary
causal test and are run in run_study.
"""
from __future__ import annotations

import torch

from experiments.phase_guided_slots_v2 import datasets_pressure_v2 as D
from experiments.phase_guided_slots_v2.task_schema import build_vocab
from .retention_model import OCfg, RetentionModel
from .train_eval import TCfg, train_curriculum, evaluate

LAMBDAS = [0.0, 0.01, 0.05, 0.10, 0.25]
STAGES = [(2, 120), (4, 150), (8, 180), (12, 200)]


def lambda_sweep(seed=0, n_live=12, lambdas=LAMBDAS):
    v = build_vocab()
    def gen_fn(nl): return D.generate(v, "train", seed, 300, nl, 8, focus_retention=True)
    out = {}
    for lam in lambdas:
        torch.manual_seed(seed)
        m = RetentionModel(OCfg(vocab_size=v.size, lambda_fixed=lam), "D-v2")
        train_curriculum(m, gen_fn, v.pad_id, STAGES, TCfg(seed=seed))
        te = D.generate(v, "test", 100 + seed, 150, n_live, 8, focus_retention=True)
        r = evaluate(m, te, v.pad_id)
        out[str(lam)] = {"survival": r["target_survival_rate"], "acc": r["answer_acc"],
                         "early_survival": r["survival_by_target_position"]["early"]}
    return out
