"""Train & cache the arm checkpoints used by the diagnostic probes (seed 0)."""
import sys
from experiments.phase_guidance_diagnostics import _common as C

ARMS = ["C", "D", "D-no-guid", "D-write-only", "D-query-only"]
PRESSURES = ["3x", "1x"]

if __name__ == "__main__":
    for pressure in PRESSURES:
        for arm in ARMS:
            m, cfg, tok, meta = C.train_or_load(arm, pressure, seed=0)
            print(f"[ckpt] {arm:14s} p{pressure} "
                  f"ans={meta['metrics']['answer_acc']:.3f} "
                  f"wF1={meta['metrics']['write_f1']:.3f}", flush=True)
    print("CKPTS DONE", flush=True)
