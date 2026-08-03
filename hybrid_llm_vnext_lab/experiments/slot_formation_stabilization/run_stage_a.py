#!/usr/bin/env python3
"""Stage A orchestrator: run every intervention arm on diagnostic seeds 3,6,7, sequentially,
writing {arm}_results.json into a shared run dir. Idempotent: an arm whose results file already
exists (with all 3 seeds) is skipped, so a long background job can resume after interruption.
A+ for Stage A is reused from the frozen artifacts (not retrained).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ARMS = ["B0", "O1", "O2", "K1", "C1", "R1", "CR1"]
SEEDS = [3, 6, 7]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="stageA")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--seeds", default="3,6,7")
    ap.add_argument("--steps", type=int, default=1200)
    args = ap.parse_args()

    try:
        import torch  # noqa: F401
    except Exception:
        print("RESOURCE_BLOCKED: torch not installed.")
        return 3

    import stabilize as SB
    out_dir = HERE / "artifacts" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    arms = [a for a in args.arms.split(",") if a]

    for arm in arms:
        rf = out_dir / f"{arm}_results.json"
        if rf.exists():
            recs = json.loads(rf.read_text())["records"]
            if {r["seed"] for r in recs} >= set(seeds):
                print(f"[stageA] SKIP {arm} (complete)", flush=True)
                continue
        records = []
        for seed in seeds:
            sf = out_dir / f"{arm}_seed{seed}.json"
            if sf.exists():
                records.append(json.loads(sf.read_text()))
                print(f"[stageA] reuse {arm} seed{seed}", flush=True)
                continue
            t0 = time.time()
            print(f"[stageA] RUN {arm} seed{seed} steps={args.steps}", flush=True)
            rec = SB.run_arm(arm, seed, steps=args.steps)
            sf.write_text(json.dumps(rec, indent=2))
            records.append(rec)
            print(f"[stageA] DONE {arm} seed{seed} needle@d96={rec['needle_by_dist']['96']:.3f} "
                  f"ppl256={rec['ppl']['256']:.1f} ({round(time.time()-t0,1)}s)", flush=True)
        rf.write_text(json.dumps({"arm": arm, "records": records}, indent=2))
        print(f"[stageA] wrote {rf}", flush=True)
        _preserve(args.run_id, arm, out_dir)
    print("[stageA] ALL ARMS COMPLETE", flush=True)
    return 0


def _preserve(run_id, arm, out_dir):
    """Durably commit+push a completed arm's raw results so the compute survives any container
    reclone. Non-fatal on failure (e.g. transient network); the next arm still proceeds."""
    import subprocess
    REPO = "/home/user/symbolu"
    files = [str(out_dir / f"{arm}_results.json")] + [str(p) for p in out_dir.glob(f"{arm}_seed*.json")]
    try:
        subprocess.run(["git", "-C", REPO, "add", "-f", *files], check=False, capture_output=True)
        msg = f"research(slots): checkpoint Stage A arm {arm} results ({run_id})"
        r = subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", msg,
                            "-m", "Automated per-arm durability checkpoint (raw diagnostic-seed results).",
                            "-m", "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>",
                            "-m", "Claude-Session: https://claude.ai/code/session_0158cnJzS81RoDfw8ptbnrnn"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            for _ in range(3):
                p = subprocess.run(["git", "-C", REPO, "push"], capture_output=True, text=True)
                if p.returncode == 0:
                    print(f"[stageA] preserved+pushed {arm}", flush=True); return
                time.sleep(4)
            print(f"[stageA] committed {arm} (push failed, will retry next arm)", flush=True)
        else:
            print(f"[stageA] preserve {arm}: nothing to commit or commit skipped", flush=True)
    except Exception as e:
        print(f"[stageA] preserve {arm} error (non-fatal): {e}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
