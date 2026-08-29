"""Training/evaluation harness. One invocation = one (arm, seed) run.

Usage:
  python -m experiments.phase_temporal_collector.harness --arm harmonic --seed 0

Data streams are generated on the fly from generator seeds shared across arms,
so every arm sees identical training, validation, and test data. Model selection
is by validation loss; the selected checkpoint is evaluated on the fixed in-dist
and held-out-frequency test sets.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .collectors import ARMS
from .reader import build_matched
from .signals import CUTOFFS, FAMILIES, FORECAST_FAMILIES, make_batch

STEPS = 800
BATCH_STREAMS = 24
LR = 2e-3
EVAL_EVERY = 100
VAL_STREAMS = 300
TEST_STREAMS = 750  # ~150 per family per split
EVENT_LOSS_W = 0.5
VAL_SEED = 10_000
TEST_SEED_IND = 20_000
TEST_SEED_HELD = 30_000

RESULTS = Path(__file__).parent / "results"


def to_torch(batch):
    return {k: torch.from_numpy(v) for k, v in batch.items()}


def losses(model, b):
    fc, ev_logit = model(b["x"], b["dt"], b["tau"], b["future_off"])
    mse = F.mse_loss(fc, b["y"])
    rare = FAMILIES.index("rare_event")
    is_rare = (b["family"] == rare).float().unsqueeze(1).expand_as(ev_logit)
    if is_rare.sum() > 0:
        bce = (F.binary_cross_entropy_with_logits(
            ev_logit, b["event"], reduction="none") * is_rare).sum() / is_rare.sum()
    else:
        bce = torch.zeros(())
    return mse + EVENT_LOSS_W * bce, fc, ev_logit


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
                 / (len(pos) * len(neg)))


@torch.no_grad()
def evaluate(model, batch):
    model.eval()
    b = to_torch(batch)
    fcs, evs = [], []
    for i in range(0, len(b["x"]), 100):  # chunk to bound memory
        s = slice(i, i + 100)
        fc, ev = model(b["x"][s], b["dt"][s], b["tau"][s], b["future_off"][s])
        fcs.append(fc)
        evs.append(ev)
    fc = torch.cat(fcs).numpy()
    ev = torch.cat(evs).numpy()
    y, fam, event = batch["y"], batch["family"], batch["event"]
    out = {}
    for fi, fname in enumerate(FAMILIES):
        m = fam == fi
        if m.sum() == 0:
            continue
        err = ((fc[m] - y[m]) ** 2).mean()
        var = y[m].var()
        out[fname] = {"nmse": float(err / var), "n": int(m.sum())}
        if fname == "rare_event":
            out[fname]["auc"] = auc(ev[m].ravel(), event[m].ravel())
    out["val_loss"] = float(np.mean([(fc - y) ** 2]))
    model.train()
    return out


def run(arm: str, seed: int):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = build_matched(arm, verbose=True)
    n_params = model.n_params()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=STEPS)

    val = make_batch(np.random.default_rng(VAL_SEED), VAL_STREAMS, heldout=False)
    test_ind = make_batch(np.random.default_rng(TEST_SEED_IND), TEST_STREAMS, heldout=False)
    test_held = make_batch(np.random.default_rng(TEST_SEED_HELD), TEST_STREAMS, heldout=True)

    best_val, best_state = float("inf"), None
    t0 = time.time()
    for step in range(1, STEPS + 1):
        rng = np.random.default_rng(1_000_000 * seed + step)  # shared across arms
        b = to_torch(make_batch(rng, BATCH_STREAMS, heldout=False))
        loss, _, _ = losses(model, b)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % EVAL_EVERY == 0 or step == STEPS:
            v = evaluate(model, val)
            vloss = float(np.mean([v[f]["nmse"] for f in FORECAST_FAMILIES]))
            if vloss < best_val:
                best_val = vloss
                best_state = {k: t.detach().clone() for k, t in model.state_dict().items()}
            print(f"[{arm} s{seed}] step {step} loss {loss.item():.4f} "
                  f"val_nmse {vloss:.4f} best {best_val:.4f} "
                  f"({time.time() - t0:.0f}s)", flush=True)

    model.load_state_dict(best_state)
    res = {
        "arm": arm, "seed": seed, "params": n_params, "steps": STEPS,
        "best_val_nmse": best_val,
        "state_floats_at_240": model.collector.state_floats(240),
        "in_dist": evaluate(model, test_ind),
        "held_out": evaluate(model, test_held),
        "wall_seconds": round(time.time() - t0, 1),
    }
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{arm}_seed{seed}.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"wrote {out}", flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--smoke", action="store_true", help="tiny run for wiring check")
    args = ap.parse_args()
    if args.smoke:
        STEPS, EVAL_EVERY, VAL_STREAMS, TEST_STREAMS = 20, 10, 40, 50
    torch.set_num_threads(4)
    run(args.arm, args.seed)
