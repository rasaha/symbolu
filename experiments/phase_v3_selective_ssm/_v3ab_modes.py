"""
_v3ab_modes.py — supplementary: V3-AB (retention + write, no C_t) under the three
supervision modes (§11). Motivated by the practical recommendation that V3-AB — not full
V3-ABC — is the strongest immediate variant, since C_t is empirically pass-through and the
two missing mechanisms are autonomous write (B_t) and content-dependent retention (γ_t).

Reports V3-AB focus decode across distance for modes A_supervised / B_annealed / C_scratch
and the annealed-retention ratio (§16.6, B/A). Writes results/v3ab_modes.json.
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from .config import SEEDS, TrainCfg, DataCfg
from .dataset import build_vocab
from .train import FocusModel, train_focus
from .distance_eval import eval_distances

HERE = Path(__file__).resolve().parent
DISTS = (256, 512, 1024, 2048)
MODES = ("A_supervised", "B_annealed", "C_scratch")


def run(seeds=SEEDS):
    vocab = build_vocab(); dcfg = DataCfg(); t0 = time.time()
    out = {m: {} for m in MODES}
    for mode in MODES:
        per = []
        for seed in seeds:
            torch.manual_seed(seed)
            m = FocusModel("V3-AB", vocab.size)
            train_focus(m, vocab, TrainCfg(seed=seed), mode=mode, dcfg=dcfg)
            dev = eval_distances(m, vocab, dcfg, DISTS, seed=seed)
            per.append(dev)
            print(f"[V3-AB {mode} s{seed}] d1024 state={dev['1024']['state_top1']:.3f} "
                  f"ctrl={max(dev['1024']['shuffled_top1'], dev['1024']['random_top1']):.3f} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        for d in map(str, DISTS):
            xs = [p[d]["state_top1"] for p in per]
            ctrl = [max(p[d]["shuffled_top1"], p[d]["random_top1"]) for p in per]
            out[mode][d] = {"state_top1_mean": st.mean(xs),
                            "state_top1_std": st.pstdev(xs) if len(xs) > 1 else 0.0,
                            "control_mean": st.mean(ctrl), "raw": xs}
    # §16.6 annealed retention ratio B/A at 1024 and 2048
    ratios = {}
    for d in ("1024", "2048"):
        a = out["A_supervised"][d]["state_top1_mean"]
        b = out["B_annealed"][d]["state_top1_mean"]
        ratios[d] = {"B_over_A": (b / a if a > 1e-6 else 0.0), "A": a, "B": b,
                     "met_0.80": (b / a if a > 1e-6 else 0.0) >= 0.80}
    result = {"by_mode": out, "annealed_retention_ratio": ratios}
    (HERE / "results" / "v3ab_modes.json").write_text(json.dumps(result, indent=2, default=float))
    print("V3AB MODES DONE", flush=True)
    return result


if __name__ == "__main__":
    run()
