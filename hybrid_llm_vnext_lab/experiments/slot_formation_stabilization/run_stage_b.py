#!/usr/bin/env python3
"""Stage B orchestrator: train A+, B0, and the SELECTED candidate on the five FRESH seeds
(8,9,10,11,12), 1200 steps, no tuning. Idempotent/resumable. The candidate id is read from
SELECTED_CANDIDATE.json unless overridden. Re-verifies pre-registration before running.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SEEDS = [8, 9, 10, 11, 12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="stageB")
    ap.add_argument("--candidate", default=None)
    ap.add_argument("--seeds", default="8,9,10,11,12")
    ap.add_argument("--steps", type=int, default=1200)
    args = ap.parse_args()

    try:
        import torch  # noqa: F401
    except Exception:
        print("RESOURCE_BLOCKED: torch not installed.")
        return 3

    # re-verify pre-registration integrity before fresh training
    pr = subprocess.run([sys.executable, str(HERE / "verify_preregistration.py")], capture_output=True, text=True)
    print(pr.stdout.strip())
    if pr.returncode != 0:
        print("ABORT: pre-registration integrity failed before Stage B")
        return 2

    cand = args.candidate
    if cand is None:
        sc = HERE / "SELECTED_CANDIDATE.json"
        if not sc.exists():
            print("ABORT: no SELECTED_CANDIDATE.json and no --candidate given")
            return 2
        sel = json.loads(sc.read_text())
        cand = sel.get("selected")
        if cand is None:
            print(f"No candidate selected ({sel.get('classification')}); Stage B not run.")
            return 0

    import stabilize as SB
    out_dir = HERE / "artifacts" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    arms = ["A+", "B0", cand]

    for arm in arms:
        rf = out_dir / f"{arm}_results.json"
        if rf.exists() and {r["seed"] for r in json.loads(rf.read_text())["records"]} >= set(seeds):
            print(f"[stageB] SKIP {arm} (complete)", flush=True)
            continue
        records = []
        for seed in seeds:
            sf = out_dir / f"{arm}_seed{seed}.json"
            if sf.exists():
                records.append(json.loads(sf.read_text())); continue
            t0 = time.time()
            print(f"[stageB] RUN {arm} seed{seed}", flush=True)
            rec = SB.run_arm(arm, seed, steps=args.steps)
            sf.write_text(json.dumps(rec, indent=2))
            records.append(rec)
            print(f"[stageB] DONE {arm} seed{seed} needle@d96={rec['needle_by_dist']['96']:.3f} "
                  f"({round(time.time()-t0,1)}s)", flush=True)
        rf.write_text(json.dumps({"arm": arm, "records": records}, indent=2))
        _preserve(args.run_id, arm, out_dir)
    print("[stageB] ALL ARMS COMPLETE", flush=True)
    return 0


def _preserve(run_id, arm, out_dir):
    """Durably commit+push a completed Stage B arm's raw results (restart-safe). Non-fatal."""
    import subprocess
    REPO = "/home/user/symbolu"
    safe = arm.replace("+", "plus")
    files = [str(out_dir / f"{arm}_results.json")] + [str(p) for p in out_dir.glob(f"{arm}_seed*.json")]
    try:
        subprocess.run(["git", "-C", REPO, "add", "-f", *files], check=False, capture_output=True)
        r = subprocess.run(["git", "-C", REPO, "commit", "-q", "-m",
                            f"research(slots): checkpoint Stage B arm {arm} results ({run_id})",
                            "-m", "Automated per-arm durability checkpoint (fresh-holdout results).",
                            "-m", "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>",
                            "-m", "Claude-Session: https://claude.ai/code/session_0158cnJzS81RoDfw8ptbnrnn"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            for _ in range(3):
                if subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True).returncode == 0:
                    print(f"[stageB] preserved+pushed {arm}", flush=True); return
                time.sleep(4)
            print(f"[stageB] committed {arm} (push retry next arm)", flush=True)
    except Exception as e:
        print(f"[stageB] preserve {arm} error (non-fatal): {e}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
