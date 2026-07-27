"""_sat_smoke.py — §11 saturation check: is there a non-saturated capacity window?"""
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
    # train the two learned arms we need for the window check
    cfgt = TrainCfg(seed=0, steps=500)
    mcond = build_router("R-COND", vocab, 0); train_router(mcond, "R-COND", vocab, cfgt, dcfg)
    mbil = build_router("R-bilinear-hard", vocab, 0); train_router(mbil, "R-bilinear-hard", vocab, cfgt, hard_cfg(dcfg))
    print(f"trained ({time.time()-t0:.0f}s)", flush=True)
    te = generate(vocab, dcfg, 64, 4, 300, 9000)   # N=64, K=4 → 16x pressure
    for arm, m in [("R-random", None), ("R-recency", None), ("R-frequency", None),
                   ("R-COND", mcond), ("R-bilinear-hard", mbil), ("R-oracle", None), ("R-unlimited", None)]:
        r = evaluate_arm(arm, m, te, vocab, 4)
        print(f"{arm}: acc={r['accuracy']:.3f} rel_recall={r['relevant_recall']:.3f} "
              f"hard_FA={r['hard_false_admit']:.3f} stream_ok={r['stream_matches_full']:.2f} ({time.time()-t0:.0f}s)", flush=True)
    print("SAT DONE", flush=True)
