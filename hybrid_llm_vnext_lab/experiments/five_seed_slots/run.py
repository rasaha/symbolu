#!/usr/bin/env python3
"""Five-seed holdout driver — reuses the FROZEN neural_slots_only harness (no model logic forked).

Verifies pre-registration integrity + the frozen abc.json digest, then runs the frozen A/A+/S
harness over the holdout seeds, and copies the result into an immutable artifact dir with a
manifest. Requires torch; exits non-zero if absent (a requested run that cannot execute is a
failure). --check-environment reports availability and exits 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parents[1]
REPO = LAB.parent
FROZEN_HARNESS = LAB / "experiments" / "neural_slots_only" / "run.py"
ABC = REPO / "experiments" / "phase_lc" / "results" / "abc.json"
ABC_SHA = "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _torch():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-environment", action="store_true")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--seeds", default="3,4,5,6,7")
    ap.add_argument("--steps", type=int, default=1200)
    args = ap.parse_args()

    if args.check_environment:
        print(json.dumps({"torch_available": _torch(), "python": sys.version.split()[0],
                          "harness": str(FROZEN_HARNESS)}, indent=2))
        return 0

    # 1. pre-registration integrity
    pr = subprocess.run([sys.executable, str(HERE / "verify_preregistration.py")],
                        capture_output=True, text=True)
    if pr.returncode != 0:
        print(pr.stdout + pr.stderr)
        print("ABORT: pre-registration integrity failed")
        return 2
    # 2. frozen artifact digest
    if ABC.exists() and _sha(ABC) != ABC_SHA:
        print("ABORT: frozen abc.json digest changed before run")
        return 2

    if not _torch():
        print("RESOURCE_BLOCKED: torch not installed; five-seed validation cannot run.")
        return 3

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    abc_before = _sha(ABC) if ABC.exists() else None

    # 3. run the FROZEN harness over the holdout seeds
    cmd = [sys.executable, str(FROZEN_HARNESS), "--run-id", f"fiveseed_{run_id}",
           "--seeds", args.seeds, "--steps", str(args.steps)]
    print(f"[five-seed] run_id={run_id} seeds={args.seeds}\n[five-seed] cmd: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd)
    wall = time.time() - t0
    if proc.returncode != 0:
        print(f"[five-seed] harness exited {proc.returncode}")
        return proc.returncode

    # 4. frozen artifact unchanged
    if ABC.exists():
        assert _sha(ABC) == abc_before, "FATAL: frozen abc.json changed during the run"

    # 5. copy result into immutable artifact dir + manifest
    src = (LAB / "experiments" / "neural_slots_only" / "artifacts" / f"fiveseed_{run_id}"
           / "slots_only_results.json")
    dest_dir = HERE / "artifacts" / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "five_seed_results.json"
    shutil.copy2(src, dest)
    manifest = {
        "run_id": run_id, "seeds": args.seeds, "steps": args.steps, "wall_s": round(wall, 1),
        "command": " ".join(cmd),
        "source_commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                        capture_output=True, text=True).stdout.strip(),
        "preregistration_sha256": (HERE / "ACCEPTANCE_GATES.sha256").read_text().strip(),
        "result_sha256": _sha(dest), "frozen_abc_sha256_unchanged": abc_before,
    }
    (dest_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[five-seed] wrote {dest}\n[five-seed] classify: python {HERE.relative_to(REPO)}/classify.py --results {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
