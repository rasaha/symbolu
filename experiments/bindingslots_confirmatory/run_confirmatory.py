#!/usr/bin/env python3
"""Confirmatory replication orchestrator: trains A+, B0, CR1 on the five FRESH seeds (13,14,15,16,17)
for the exact frozen 1200-step budget, no tuning. Idempotent / resumable (per-seed JSON files;
skip if present). Re-verifies the confirmatory pre-registration integrity before any training.

Reuses the FROZEN Stage B harness (stabilize.run_arm) unchanged. CR1's curriculum + temporary
alignment schedule are exactly the merged configuration. Records restart/resume events into a
run manifest. Requires torch.

CLI:  python run_confirmatory.py [--seeds 13,14,15,16,17] [--arms A+,B0,CR1] [--steps 1200]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
NEURAL = REPO / "hybrid_llm_vnext_lab" / "experiments" / "neural_slots_only"
for p in (str(SBS), str(NEURAL)):
    if p not in sys.path:
        sys.path.insert(0, p)

SEEDS = [13, 14, 15, 16, 17]
ARMS = ["A+", "B0", "CR1"]
RESULTS = HERE / "results"
SEED_DIR = RESULTS / "seeds"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def config_hash() -> str:
    return sha256_file(HERE / "frozen_cr1_config.json")


def env_fingerprint():
    import torch
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "num_threads": torch.get_num_threads(),
        "fp": "fp32",
    }


def code_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO)).decode().strip()
    except Exception:
        return "unknown"


def _arm_file(arm):
    return SEED_DIR / f"{arm}_results.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="13,14,15,16,17")
    ap.add_argument("--arms", default="A+,B0,CR1")
    ap.add_argument("--steps", type=int, default=1200)
    args = ap.parse_args()

    # integrity gate before ANY training
    pr = subprocess.run([sys.executable, str(HERE / "verify_confirmatory_prereg.py")],
                        capture_output=True, text=True)
    print(pr.stdout.strip())
    if pr.returncode != 0:
        print("ABORT: confirmatory pre-registration integrity failed")
        return 2

    try:
        import torch  # noqa: F401
    except Exception:
        print("CONFIRMATORY_RESOURCE_BLOCKED: torch not installed; confirmatory run cannot execute.")
        return 3

    import stabilize as SB

    seeds = [int(s) for s in args.seeds.split(",")]
    arms = [a for a in args.arms.split(",")]
    assert seeds == SEEDS, f"fresh seeds are frozen to {SEEDS}; refusing {seeds}"
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = RESULTS / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {
            "schema": "bindingslots_confirmatory/run_manifest/v1",
            "code_commit": code_commit(),
            "frozen_cr1_config_sha256": config_hash(),
            "classifier_sha256": sha256_file(HERE / "classifier.json"),
            "fresh_seeds": SEEDS,
            "arms": arms,
            "environment": env_fingerprint(),
            "abc_json_sha256_before": sha256_file(REPO / "experiments/phase_lc/results/abc.json"),
            "abc_json_sha256_after": None,
            "restart_events": [],
            "seed_arm_status": {},
        }
    # record this process start as a (re)start/resume event
    manifest["restart_events"].append({"event": "orchestrator_start", "ts_monotonic": round(time.monotonic(), 3)})
    manifest_path.write_text(json.dumps(manifest, indent=2))

    for arm in arms:
        af = _arm_file(arm)
        done = set()
        records = []
        if af.exists():
            records = json.loads(af.read_text())["records"]
            done = {r["seed"] for r in records}
        for seed in seeds:
            sf = SEED_DIR / f"{arm}_seed{seed}.json"
            if sf.exists():
                if seed not in done:
                    records.append(json.loads(sf.read_text()))
                    done.add(seed)
                continue
            t0 = time.time()
            print(f"[conf] RUN {arm} seed{seed}", flush=True)
            rec = SB.run_arm(arm, seed, steps=args.steps)
            # enrich with confirmatory provenance
            rec["schema"] = "bindingslots_confirmatory/seed_result/v1"
            rec["config_hash"] = config_hash()
            rec["code_commit"] = manifest["code_commit"]
            rec["environment_fingerprint"] = manifest["environment"]
            rec["checkpoint_steps"] = [0, 60, 120, 300, 600, 900, 1200]
            sf.write_text(json.dumps(rec, indent=2))
            records.append(rec)
            manifest.setdefault("seed_arm_status", {})[f"{arm}_seed{seed}"] = "complete"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            print(f"[conf] DONE {arm} seed{seed} needle@d96={rec['needle_by_dist']['96']:.3f} "
                  f"({round(time.time()-t0,1)}s)", flush=True)
        af.write_text(json.dumps({"arm": arm, "records": sorted(records, key=lambda r: r['seed'])}, indent=2))

    manifest["abc_json_sha256_after"] = sha256_file(REPO / "experiments/phase_lc/results/abc.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("[conf] ALL ARMS COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
