"""_smoke.py — fast end-to-end pipeline check: train V1/V2-S/V3-ABC, probe focus decode."""
from __future__ import annotations
import time
import torch

from .config import DataCfg, TrainCfg
from .dataset import build_vocab
from .train import FocusModel, train_focus
from .focus_probe import probe_all

if __name__ == "__main__":
    t0 = time.time()
    vocab = build_vocab()
    dcfg = DataCfg()
    # short curriculum for the smoke
    cfg = TrainCfg(seed=0, stages=[(32, 120), (64, 150), (128, 180)])
    for name in ("V1", "V2-S", "V3-ABC"):
        torch.manual_seed(0)
        m = FocusModel(name, vocab.size)
        train_focus(m, vocab, cfg, mode="B_annealed", dcfg=dcfg)
        line = [f"{name}"]
        for dist in (128, 256):
            r = probe_all(m, vocab, dcfg, dist, seed=0, n_train=400, n_eval=300)
            line.append(f"d{dist}: state={r['state']['top1']:.3f} "
                        f"sel={r['selective_readout']['top1']:.3f} "
                        f"shuf={r['shuffled_state']['top1']:.3f} "
                        f"rand={r['random_state']['top1']:.3f} "
                        f"relF1={r['relevance']['f1']:.3f}")
        print(" | ".join(line) + f"  ({time.time()-t0:.0f}s)", flush=True)
    print(f"SMOKE DONE {time.time()-t0:.0f}s", flush=True)
