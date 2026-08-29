"""Training/evaluation harness. One invocation = one (arm, seed) run.

Usage:
  python -m experiments.phase_temporal_collector.harness --arm harmonic --seed 0

Data streams are generated on the fly from generator seeds shared across arms,
so every arm sees identical training, validation, and test data. Model selection
is by validation loss; the selected checkpoint is evaluated on the fixed test
splits.

Amendment 2: training supervision is densified — arm F (raw_quad) trains
causally at every position in [16, 240); summary arms train at 16 cutoff
positions sampled per batch from [32, 240]. Evaluation is UNCHANGED: the gated
metric is computed at the frozen cutoffs {128, 192, 240}. Two informational
test splits (extrapolation periods, drifting frequency) are reported but never
gated.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .collectors import ARM_NAMES
from .reader import build_matched
from .signals import CUTOFFS, FAMILIES, FORECAST_FAMILIES, H, make_batch

STEPS = 4000  # Amendment 1 budget, retained by Amendment 2
BATCH_STREAMS = 24
LR = 2e-3
EVAL_EVERY = 250
N_TRAIN_CUTS = 16                     # Amendment 2: sampled cutoffs, summary arms
TRAIN_CUT_RANGE = (32, 240)           # inclusive t_c range for sampled cutoffs
DENSE_POSITIONS = list(range(16, 240))  # last-observed indices for causal F
VAL_STREAMS = 300
TEST_STREAMS = 750   # ~150 per family per split
DRIFT_TEST_STREAMS = 150
EVENT_LOSS_W = 0.5
VAL_SEED = 10_000
TEST_SEED_IND = 20_000
TEST_SEED_HELD = 30_000
TEST_SEED_EXTRAP = 40_000
TEST_SEED_DRIFT = 50_000

RESULTS = Path(__file__).parent / "results"
RARE_IDX = FAMILIES.index("rare_event")


def _windows(a: np.ndarray, w: int) -> np.ndarray:
    return np.lib.stride_tricks.sliding_window_view(a, w, axis=1)


def targets_at(batch: dict, cuts) -> dict:
    """Targets/future offsets/events at arbitrary cutoff positions t_c."""
    x, tau, on = batch["x"], batch["tau"], batch["onsets"]
    wx, wt, wo = _windows(x, H), _windows(tau, H), _windows(on, H)
    idx = np.asarray(cuts)
    y = wx[:, idx]                                        # [B, C, H]
    fut = wt[:, idx] - tau[:, idx - 1, None]
    ev = wo[:, idx].max(-1)
    return {"y": y.astype(np.float32), "future_off": fut.astype(np.float32),
            "event": ev.astype(np.float32)}


def composite_loss(fc, ev_logit, y, event, family):
    mse = F.mse_loss(fc, y)
    is_rare = (family == RARE_IDX).float().unsqueeze(1).expand_as(ev_logit)
    if is_rare.sum() > 0:
        bce = (F.binary_cross_entropy_with_logits(
            ev_logit, event, reduction="none") * is_rare).sum() / is_rare.sum()
    else:
        bce = torch.zeros(())
    return mse + EVENT_LOSS_W * bce


def train_step(model, batch, cut_rng):
    x = torch.from_numpy(batch["x"])
    dt = torch.from_numpy(batch["dt"])
    tau = torch.from_numpy(batch["tau"])
    family = torch.from_numpy(batch["family"])
    if model.arm == "raw_quad":
        positions = DENSE_POSITIONS
        tg = targets_at(batch, [p + 1 for p in positions])  # t_c = position + 1
        fc, ev = model.forward_dense(x, dt, tau,
                                     torch.from_numpy(tg["future_off"]), positions)
    else:
        lo, hi = TRAIN_CUT_RANGE
        cuts = np.sort(cut_rng.choice(np.arange(lo, hi + 1), size=N_TRAIN_CUTS,
                                      replace=False))
        tg = targets_at(batch, cuts)
        fc, ev = model.forward_at(x, dt, tau,
                                  torch.from_numpy(tg["future_off"]), list(cuts))
    return composite_loss(fc, ev, torch.from_numpy(tg["y"]),
                          torch.from_numpy(tg["event"]), family)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
                 / (len(pos) * len(neg)))


@torch.no_grad()
def evaluate(model, batch):
    """Frozen-cutoff evaluation ({128, 192, 240}) — unchanged across sweeps."""
    model.eval()
    fcs, evs = [], []
    for i in range(0, len(batch["x"]), 100):
        s = slice(i, i + 100)
        fc, ev = model.forward_at(
            torch.from_numpy(batch["x"][s]), torch.from_numpy(batch["dt"][s]),
            torch.from_numpy(batch["tau"][s]),
            torch.from_numpy(batch["future_off"][s]), list(CUTOFFS))
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
    model.train()
    return out


def run(arm: str, seed: int):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = build_matched(arm, verbose=True)
    n_params = model.n_params()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=STEPS)

    val = make_batch(np.random.default_rng(VAL_SEED), VAL_STREAMS, mode="train")
    test_ind = make_batch(np.random.default_rng(TEST_SEED_IND), TEST_STREAMS, mode="train")
    test_held = make_batch(np.random.default_rng(TEST_SEED_HELD), TEST_STREAMS, mode="heldout")
    test_extrap = make_batch(np.random.default_rng(TEST_SEED_EXTRAP), TEST_STREAMS, mode="extrap")
    test_drift = make_batch(np.random.default_rng(TEST_SEED_DRIFT), DRIFT_TEST_STREAMS,
                            mode="train", families=("freq_drift",))

    best_val, best_state = float("inf"), None
    t0 = time.time()
    for step in range(1, STEPS + 1):
        rng = np.random.default_rng(1_000_000 * seed + step)  # shared across arms
        b = make_batch(rng, BATCH_STREAMS, mode="train")
        loss = train_step(model, b, rng)
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
        "state_floats_at_240": model.state_floats(240),
        "in_dist": evaluate(model, test_ind),
        "held_out": evaluate(model, test_held),
        "extrap": evaluate(model, test_extrap),
        "freq_drift": evaluate(model, test_drift),
        "wall_seconds": round(time.time() - t0, 1),
    }
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{arm}_seed{seed}.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"wrote {out}", flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARM_NAMES))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--smoke", action="store_true", help="tiny run for wiring check")
    args = ap.parse_args()
    if args.smoke:
        STEPS, EVAL_EVERY, VAL_STREAMS, TEST_STREAMS, DRIFT_TEST_STREAMS = 20, 10, 40, 50, 30
    torch.set_num_threads(4)
    run(args.arm, args.seed)
