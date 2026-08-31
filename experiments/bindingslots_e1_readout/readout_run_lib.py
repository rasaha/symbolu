#!/usr/bin/env python3
"""Shared execution helpers for the readout diagnostic: train+evaluate every arm on a frozen encoder for a
seed, verify frozen-base hashes unchanged, record metrics/params/hashes/activity, R1-vs-R2 distinctness,
determinism replay, and runtime oracle-equivariance. Reuses the factorial evaluator for the metric set."""
from __future__ import annotations

import json
import pathlib
import sys

import torch

FACTOR_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_3factor"
if str(FACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(FACTOR_DIR))
import factor_eval as EV              # noqa: E402  (reused null-inclusive T4 partition evaluator)

import readout_config as C           # noqa: E402
from readout_model import Readout, build_frozen_encoder   # noqa: E402
from readout_train import train_readout, readout_hash, base_hash, param_hash, readout_activity  # noqa: E402

RES = pathlib.Path(__file__).resolve().parent / "results"
RES.mkdir(exist_ok=True)


def write_json(name, obj):
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2, sort_keys=True)); tmp.replace(p)
    return p


def added_params(enc, arm):
    return Readout(enc, arm).added_params()


def run_seed(enc, train_eps, seed, arms=None):
    """Train+eval every arm on one seed's shared cohort. Frozen-base hash verified unchanged per arm."""
    arms = arms or list(C.ARMS)
    cohort = EV.build_cohort(seed)
    frozen_base_ref = base_hash(Readout(enc, "R0"))
    out = {}
    for arm in arms:
        m, b_before, b_after = train_readout(enc, arm, train_eps, seed)
        metrics = EV.eval_cell(m, cohort)
        out[arm] = {
            "metrics": metrics,
            "added_params": m.added_params(),
            "head_param_breakdown": m.head_param_breakdown(),
            "readout_hash": readout_hash(m),
            "base_hash_before": b_before, "base_hash_after": b_after,
            "frozen_base_unchanged": (b_before == b_after == frozen_base_ref),
            "readout_activity": readout_activity(m),
        }
    return out, cohort


def r1_r2_distinctness(enc, train_eps, seed):
    """Prove R2 is genuinely distinct from R1 (not two copies of one single-head form) and its heads do not
    collapse: report head-parameter cosine, attention-distribution divergence, and R1-vs-R2 disagreement."""
    m1, _, _ = train_readout(enc, "R1", train_eps, seed)   # training needs grad; do NOT wrap in no_grad
    m2, _, _ = train_readout(enc, "R2", train_eps, seed)
    cohort = EV.build_cohort(seed)
    eps = cohort["T4_latest"]
    import temporal_task as T
    with torch.no_grad():
        kt = torch.tensor([e["key_tokens"] for e in eps]); qt = torch.tensor([e["query_tokens"] for e in eps])
        p1 = m1.scores(kt, qt).argmax(-1); p2 = m2.scores(kt, qt).argmax(-1)
        disagree = float((p1 != p2).float().mean())
        va = torch.cat([p.flatten() for _, p in m2.head_a.named_parameters()])
        vb = torch.cat([p.flatten() for _, p in m2.head_b.named_parameters()])
        head_cos = float(torch.nn.functional.cosine_similarity(va, vb, dim=0))
        qs = m2._q_summary(qt); tok = m2._key_tokens_emb(kt); pad = (kt != T.PAD)
        _, aa = m2.head_a(tok, qs, pad); _, ab = m2.head_b(tok, qs, pad)
        attn_l1 = float((aa - ab).abs().sum(-1).mean())
    return {"r1_r2_pred_disagreement": disagree, "r2_head_param_cosine": head_cos,
            "r2_head_attn_mean_L1": attn_l1,
            "distinct": bool(disagree > 0.0 and head_cos < 0.999 and attn_l1 > 1e-3)}


@torch.no_grad()
def oracle_equivariance_check(enc, seed, arm="R2"):
    """Permuting candidate order permutes the per-candidate scores identically (null invariant): candidate
    order carries no target information."""
    m = Readout(enc, arm)
    cohort = EV.build_cohort(seed)
    eps = cohort["T4_latest"][:16]
    import temporal_task as T
    kt = torch.tensor([e["key_tokens"] for e in eps]); qt = torch.tensor([e["query_tokens"] for e in eps])
    K = kt.size(1)
    base = m.scores(kt, qt)
    perm = torch.randperm(K)
    permuted = m.scores(kt[:, perm, :], qt)
    ok_real = torch.allclose(permuted[:, :K], base[:, perm], atol=1e-6)
    ok_null = torch.allclose(permuted[:, K], base[:, K], atol=1e-6)
    return {"pass": bool(ok_real and ok_null), "real_equivariant": bool(ok_real), "null_invariant": bool(ok_null)}


def determinism_replay(enc, train_eps, seed, arm="R2"):
    h1 = readout_hash(train_readout(enc, arm, train_eps, seed)[0])
    h2 = readout_hash(train_readout(enc, arm, train_eps, seed)[0])
    return {"arm": arm, "seed": seed, "readout_hash": h1, "byte_identical": h1 == h2}
