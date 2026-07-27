"""_pressure_smoke.py — find a non-saturated window (§11): random low, COND mid, oracle high."""
from __future__ import annotations
import time
from .config import DataCfg, TrainCfg
from .capacity_dataset import build_vocab, generate
from .routers import build_router
from .train import train_router
from .evaluate import evaluate_arm
from .hard_negatives import hard_cfg

if __name__ == "__main__":
    t0 = time.time()
    vocab = build_vocab(); dcfg = DataCfg(family="single")
    cfgt = TrainCfg(seed=0, steps=500)
    mcond = build_router("R-COND", vocab, 0); train_router(mcond, "R-COND", vocab, cfgt, dcfg)
    mbil = build_router("R-bilinear-hard", vocab, 0); train_router(mbil, "R-bilinear-hard", vocab, cfgt, hard_cfg(dcfg))
    print(f"trained ({time.time()-t0:.0f}s)", flush=True)
    for N, K in [(32, 2), (64, 2), (64, 4), (128, 4), (128, 8)]:
        te = generate(vocab, dcfg, N, K, 300, 9000)
        row = {}
        for arm, m in [("R-random", None), ("R-COND", mcond), ("R-bilinear-hard", mbil), ("R-oracle", None)]:
            r = evaluate_arm(arm, m, te, vocab, K)
            row[arm] = (r["accuracy"], r["relevant_recall"], r["hard_false_admit"])
        print(f"N={N} K={K} ({N//K}x): " + " | ".join(
            f"{a}: acc={v[0]:.3f} rr={v[1]:.3f}" for a, v in row.items()) + f"  ({time.time()-t0:.0f}s)", flush=True)
    print("PRESSURE DONE", flush=True)
