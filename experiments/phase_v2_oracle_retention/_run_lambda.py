"""_run_lambda.py — run the §7/§13 λ ablation sweep and dump results/lambda_sweep.json."""
from __future__ import annotations
import json, time
from pathlib import Path
from .ablations import lambda_sweep

HERE = Path(__file__).resolve().parent
if __name__ == "__main__":
    t0 = time.time()
    out = {"n_live": 12, "seed": 0}
    out["sweep"] = lambda_sweep(seed=0, n_live=12)
    (HERE / "results" / "lambda_sweep.json").write_text(json.dumps(out, indent=2, default=float))
    for lam, r in out["sweep"].items():
        print(f"lambda={lam}: surv={r['survival']:.3f} early={r['early_survival']:.3f} "
              f"acc={r['acc']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    print(f"LAMBDA DONE {time.time()-t0:.0f}s", flush=True)
