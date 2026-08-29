"""Train all reader arms x seeds on train days, select on the dev period.

Development-envelope code: touches only bins < 960 (train t in [96, 756], dev
queries t in {768, 772, ..., 948}). Checkpoints go to the scratchpad; dev-loss
records go to results/dev_metrics.json. The held-out evaluator is separate and
runs only after the freeze commit.

Usage: python -m experiments.harmonic_real_data.train <cohort_npz> <model_dir>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as TF

from .arms import READER_ARMS, build_matched
from .data_assembly import Assembled

STEPS = 3000
BATCH = 256
LR = 1e-3
EVAL_EVERY = 250
TRAIN_T = (96, 756)
DEV_T = list(range(768, 949, 4))
SEEDS = (0, 1, 2)
RESULTS = Path(__file__).parent / "results"


def dev_eval(model, data):
    model.eval()
    losses = []
    with torch.no_grad():
        for f0 in range(0, data.n_func, 50):
            fs = np.arange(f0, min(f0 + 50, data.n_func))
            f_idx = np.repeat(fs, len(DEV_T))
            t_idx = np.tile(np.array(DEV_T), len(fs))
            toks, q, y = data.tokens(model.arm, f_idx, t_idx)
            losses.append(TF.mse_loss(model(toks, q), y).item() * len(f_idx))
    model.train()
    return sum(losses) / (data.n_func * len(DEV_T))


def train_one(data, arm, seed, model_dir):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = build_matched(arm, verbose=(seed == 0))
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=STEPS)
    best, best_state, curve = float("inf"), None, []
    t0 = time.time()
    for step in range(1, STEPS + 1):
        rng = np.random.default_rng(1_000_000 * seed + step)
        f_idx = rng.integers(0, data.n_func, BATCH)
        t_idx = rng.integers(TRAIN_T[0], TRAIN_T[1] + 1, BATCH)
        toks, q, y = data.tokens(arm, f_idx, t_idx)
        loss = TF.mse_loss(model(toks, q), y)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % EVAL_EVERY == 0:
            d = dev_eval(model, data)
            curve.append({"step": step, "dev_mse": d})
            if d < best:
                best = d
                best_state = {k: v.detach().clone()
                              for k, v in model.state_dict().items()}
    torch.save(best_state, Path(model_dir) / f"{arm}_seed{seed}.pt")
    print(f"[{arm} s{seed}] best dev MSE {best:.5f} "
          f"({time.time() - t0:.0f}s)", flush=True)
    return {"arm": arm, "seed": seed, "best_dev_mse": best,
            "params": model.n_params(), "curve": curve}


def main(npz_path, model_dir, suffix=""):
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    torch.set_num_threads(4)
    data = Assembled(npz_path)
    print("assembled tracks", flush=True)
    recs = [train_one(data, arm, seed, model_dir)
            for arm in READER_ARMS for seed in SEEDS]
    out = RESULTS / f"dev_metrics{suffix}.json"
    out.write_text(json.dumps(recs, indent=1))
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:4]))
