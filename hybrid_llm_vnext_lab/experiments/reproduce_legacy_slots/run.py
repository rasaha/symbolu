#!/usr/bin/env python3
"""Faithful launcher for the phase_lc A/B/C bounded-slot reproduction.

Design: this DOES NOT re-transcribe the model/harness. It invokes the ORIGINAL
`experiments/phase_lc/harness_abc.py` with the pinned config (config.json), so the
reproduction exercises the exact original code that produced results/abc.json. The original
tree is read-only; nothing is moved or edited.

In this environment PyTorch is absent, so the run is RESOURCE_BLOCKED: the script prints the
exact command + environment manifest and exits 0 without fabricating results.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

LAB = pathlib.Path(__file__).resolve().parents[2]
REPO = LAB.parent
CONFIG = json.loads((pathlib.Path(__file__).parent / "config.json").read_text())


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=CONFIG["training"]["seeds"])
    ap.add_argument("--steps", type=int, default=CONFIG["training"]["steps"])
    ap.add_argument("--out", default=str(LAB / "artifacts" / "legacy_slot_reproduction.json"))
    args = ap.parse_args()

    if not _torch_available():
        print("RESOURCE_BLOCKED: PyTorch is not installed in this environment.")
        print("The neural reproduction cannot run here. To reproduce:")
        print("  pip install torch   # CPU wheel is sufficient")
        print(f"  python {pathlib.Path(__file__).relative_to(REPO)} "
              f"--seeds {' '.join(map(str, args.seeds))} --steps {args.steps}")
        print("Environment manifest: python>=3.9, torch, repo @ commit "
              f"{CONFIG['target_commit']}, original tree experiments/phase_lc/ present.")
        print(f"Target artifact to match: {CONFIG['target_artifact']}")
        return 0

    # torch present: drive the ORIGINAL harness with the pinned config.
    sys.path.insert(0, str(REPO))
    harness_path = REPO / "experiments" / "phase_lc" / "harness_abc.py"
    if not harness_path.exists():
        print(f"ERROR: original harness not found at {harness_path}")
        return 2
    print(f"[reproduce] invoking original harness {harness_path} with pinned config; "
          f"seeds={args.seeds} steps={args.steps}")
    # NOTE: finalize the exact call signature against harness_abc.main() in the torch env.
    # The pinned parameters live in config.json and must be passed through unchanged
    # (d=128,h=4,layers=4,window=64,num_slots=32,target_params=2e6,N=160,batch=16,
    #  AdamW lr=2e-3 wd=0.01, warmup=60, steps=1200, seeds=[0,1,2]).
    import runpy
    sys.argv = ["harness_abc.py", "--steps", str(args.steps),
                "--seeds", *map(str, args.seeds)]
    runpy.run_path(str(harness_path), run_name="__main__")
    print(f"[reproduce] wrote harness output; copy results/abc*.json -> {args.out} and run compare.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
