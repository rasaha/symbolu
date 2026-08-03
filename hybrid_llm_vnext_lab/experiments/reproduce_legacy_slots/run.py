#!/usr/bin/env python3
"""Hardened launcher for the phase_lc A/B/C bounded-slot reproduction.

Design: invokes the ORIGINAL experiments/phase_lc/harness_abc.py (read-only) via subprocess
with the pinned config, then copies the fresh result into an immutable lab artifact directory.
It NEVER overwrites the frozen historical artifacts (results/abc.json, results/abc_partial.json)
and refuses any tag that could collide with them.

Modes:
  --check-environment : report torch/numpy availability + env, exit 0 (RESOURCE_BLOCKED-safe).
  (default)           : run the reproduction. Requires torch; if torch is absent the run
                        EXITS NON-ZERO (an explicitly requested neural run that cannot execute
                        is a failure, not a silent success).

Verified against the live harness argparse (experiments/phase_lc/harness_abc.py):
  --arms (comma)  --seeds (comma)  --steps  --N  --num_slots  --target_params  --tag
  output: results/<tag>.json  and  results/<tag>_partial.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

LAB = pathlib.Path(__file__).resolve().parents[2]
REPO = LAB.parent
PHASE_LC = REPO / "experiments" / "phase_lc"
HARNESS = PHASE_LC / "harness_abc.py"
FROZEN = {"abc", "abc_partial"}  # tags whose output files are the frozen historical artifacts
CONFIG = json.loads((pathlib.Path(__file__).parent / "config.json").read_text())


def _sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _torch():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _env_report() -> dict:
    rep = {"python": sys.version.split()[0]}
    for mod in ("torch", "numpy"):
        try:
            m = __import__(mod)
            rep[mod] = getattr(m, "__version__", "unknown")
        except Exception:
            rep[mod] = None
    return rep


def _validate_tag(tag: str) -> None:
    if tag in FROZEN or tag.startswith("abc"):
        raise SystemExit(f"REFUSED: tag {tag!r} could collide with the frozen historical "
                         f"artifact results/abc*.json. Use a unique tag (e.g. repro_slots_1200_<id>).")
    out = PHASE_LC / "results" / f"{tag}.json"
    frozen_paths = {(PHASE_LC / 'results' / 'abc.json').resolve(),
                    (PHASE_LC / 'results' / 'abc_partial.json').resolve()}
    if out.resolve() in frozen_paths:
        raise SystemExit(f"REFUSED: reproduction output {out} equals a frozen artifact path.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-environment", action="store_true",
                    help="report torch/numpy availability and exit 0")
    ap.add_argument("--run-id", default=None, help="unique run id (default: timestamp)")
    ap.add_argument("--tag", default=None, help="harness tag (default: repro_slots_1200_<run-id>)")
    ap.add_argument("--arms", default="A,B,C")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--N", type=int, default=160)
    ap.add_argument("--num-slots", type=int, default=32)
    ap.add_argument("--target-params", type=int, default=2000000)
    args = ap.parse_args()

    if args.check_environment:
        print(json.dumps({"mode": "check-environment", "env": _env_report(),
                          "torch_available": _torch(),
                          "harness_present": HARNESS.exists()}, indent=2))
        return 0

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = args.tag or f"repro_slots_1200_{run_id}"
    _validate_tag(tag)

    if not _torch():
        print("RESOURCE_BLOCKED: PyTorch is not installed; the neural reproduction cannot run.")
        print("Install a CPU wheel and re-run:")
        print("  python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu 'numpy<2' torch")
        print(f"  python {pathlib.Path(__file__).relative_to(REPO)} --run-id {run_id}")
        print(f"Target artifact to match: {CONFIG['target_artifact']}")
        return 3  # explicit non-zero: requested neural run could not execute

    if not HARNESS.exists():
        print(f"ERROR: original harness not found at {HARNESS}")
        return 2

    # pre-run: record the frozen artifact digest so we can prove it is untouched afterwards
    frozen = PHASE_LC / "results" / "abc.json"
    frozen_before = _sha256(frozen) if frozen.exists() else None

    cmd = [sys.executable, "harness_abc.py",
           "--arms", args.arms, "--seeds", args.seeds, "--steps", str(args.steps),
           "--N", str(args.N), "--num_slots", str(args.num_slots),
           "--target_params", str(args.target_params), "--tag", tag]
    print(f"[reproduce] run_id={run_id} tag={tag}\n[reproduce] cmd (cwd={PHASE_LC}): {' '.join(cmd)}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(PHASE_LC))
    wall = time.time() - t0
    if proc.returncode != 0:
        print(f"[reproduce] harness exited {proc.returncode}")
        return proc.returncode

    # frozen artifact must be byte-identical after the run
    if frozen.exists():
        assert _sha256(frozen) == frozen_before, "FATAL: frozen abc.json changed during the run!"

    # copy the fresh result into an immutable lab artifact dir + manifest
    src = PHASE_LC / "results" / f"{tag}.json"
    dest_dir = LAB / "artifacts" / "neural_reproduction" / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{tag}.json"
    shutil.copy2(src, dest)
    manifest = {
        "run_id": run_id, "tag": tag, "wall_s": round(wall, 1),
        "command": " ".join(cmd), "cwd": str(PHASE_LC),
        "source_commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                        capture_output=True, text=True).stdout.strip(),
        "env": _env_report(),
        "original_output_path": str(src), "copied_artifact_path": str(dest),
        "result_sha256": _sha256(dest),
        "frozen_abc_sha256_unchanged": frozen_before,
    }
    (dest_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[reproduce] wrote {dest}\n[reproduce] manifest {dest_dir/'run_manifest.json'}")
    print(f"[reproduce] now: python {pathlib.Path(__file__).parent.relative_to(REPO)}/compare.py "
          f"--got {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
