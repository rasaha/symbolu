#!/usr/bin/env python3
"""Shared per-seed run: train B0 + E1 on the fixed train episodes (model seed varies init + sampling),
evaluate on the requested pool's G1..G7 splits, collapse metrics, evaluate gates. Used by both the dev
calibration (dev pool) and the reserved go/no-go (final pool)."""
from __future__ import annotations

import task as T
import config as C
import engine as E
import gates as G


def eval_splits_for(pool_key, seed):
    pool = T.identity_pools(C.POOL_SALT)[pool_key]
    n = C.DEV_EVAL_N_PER_SPLIT if pool_key == "dev" else C.RESERVED_EVAL_N_PER_SPLIT
    return T.build_eval_splits(pool, n, seed_base=seed)


def run_seed(seed, pool_key, train_eps=None):
    train_eps = train_eps if train_eps is not None else C.build_train_episodes()
    e1, e1_losses = E.train_e1(train_eps, C.STEPS, C.BATCH, C.LR, C.TAU, seed=seed)
    b0, b0_losses = E.train_b0(train_eps, C.STEPS, C.BATCH, C.LR, seed=seed)
    splits = eval_splits_for(pool_key, seed)
    e1_splits = {name: E.eval_e1(e1, eps, C.TAU) for name, eps in splits.items()}
    b0_splits = {name: E.eval_b0(b0, eps) for name, eps in splits.items()}
    b0_g1_e2e = b0_splits["G1_unseen_identity"]["e2e_retrieval_accuracy"]
    collapsed = G.seed_metrics(e1_splits, b0_g1_e2e)
    seed_gates = G.eval_seed_gates(collapsed)
    return {
        "seed": seed, "pool": pool_key,
        "metrics": collapsed, "gates": seed_gates,
        "e1_splits": e1_splits, "b0_splits": b0_splits,
        "e1_param_sha256": E.param_hash(e1), "b0_param_sha256": E.param_hash(b0),
        "e1_final_loss": e1_losses[-1], "b0_final_loss": b0_losses[-1],
    }
