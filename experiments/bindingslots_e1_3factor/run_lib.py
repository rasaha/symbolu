#!/usr/bin/env python3
"""Shared execution helpers for the factorial: train+evaluate all cells for a seed, record every required
metric, param count, factor activity, and param hash; determinism replay; runtime oracle-equivariance
check. Used by both dev_run and final_run so dev and final share identical logic."""
from __future__ import annotations

import json
import pathlib

import torch

import factor_config as C
import factor_eval as EV
from factor_model import E1F
from factor_train import train_cell, param_hash, factor_activity

RES = pathlib.Path(__file__).resolve().parent / "results"
RES.mkdir(exist_ok=True)


def write_json(name, obj):
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
    tmp.replace(p)
    return p


def added_params_for(cell):
    m = E1F(factors=C.CELLS[cell])
    fpc = m.factor_param_counts()
    return int(sum(fpc[f] for f in ("F1", "F2", "F3")))


def run_seed(train_eps, seed, cells=None):
    """Train+eval every cell on one seed's shared cohort. Returns {cell: {metrics, hash, activity, ...}}."""
    cells = cells or list(C.CELLS.keys())
    cohort = EV.build_cohort(seed)
    out = {}
    for cell in cells:
        m = train_cell(train_eps, cell, seed)
        metrics = EV.eval_cell(m, cohort)
        out[cell] = {
            "factors": list(C.CELLS[cell]),
            "metrics": metrics,
            "param_hash": param_hash(m),
            "factor_param_counts": m.factor_param_counts(),
            "added_params": int(sum(m.factor_param_counts().values())),
            "base_params": m.base_param_count(),
            "factor_activity": factor_activity(m),
        }
    return out, cohort


@torch.no_grad()
def oracle_equivariance_check(seed, cell="111"):
    """Runtime proof that candidate ORDER carries no target information: permuting the key set permutes
    the model's per-candidate scores identically. If the model exploited position/oracle, this breaks."""
    m = E1F(factors=C.CELLS[cell])          # untrained is sufficient: it's a structural property of scores()
    cohort = EV.build_cohort(seed)
    eps = cohort["T4_latest"][:16]
    kt = torch.tensor([e["key_tokens"] for e in eps])
    qt = torch.tensor([e["query_tokens"] for e in eps])
    K = kt.size(1)
    base = m.scores(kt, qt, C.TAU)
    perm = torch.randperm(K)
    kt_p = kt[:, perm, :]
    permuted = m.scores(kt_p, qt, C.TAU)
    # real-candidate scores must follow the permutation exactly; null (index K) unchanged
    ok_real = torch.allclose(permuted[:, :K], base[:, perm], atol=1e-6)
    ok_null = torch.allclose(permuted[:, K], base[:, K], atol=1e-6)
    return {"pass": bool(ok_real and ok_null), "real_equivariant": bool(ok_real), "null_invariant": bool(ok_null)}


def determinism_replay(train_eps, seed, cell):
    """Retrain the same cell/seed and confirm a byte-identical param hash."""
    h1 = param_hash(train_cell(train_eps, cell, seed))
    h2 = param_hash(train_cell(train_eps, cell, seed))
    return {"cell": cell, "seed": seed, "hash": h1, "byte_identical": h1 == h2}
