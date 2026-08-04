#!/usr/bin/env python3
"""Functional-routing Stage-1 runner.

Runs R0 / O1 / O2 / H3 by executing the FROZEN `stabilize.run_arm('CR1', seed)` loop with exactly
ONE frozen function swapped in memory for the duration of the run:

  R0  -> no swap (byte-identical to merged CR1)
  O1  -> interventions.alignment_loss  := objectives.correct_slot_prob_loss
  O2  -> interventions.alignment_loss  := objectives.address_margin_loss
  H3  -> interventions.curriculum_batch := curriculum_gradual.curriculum_batch_gradual

The interventions.py / stabilize.py files on disk are NEVER edited (their sha256 are preserved and
verified). The swap is restored in a finally block, so every run leaves the module pristine. This is
the entire training-only intervention surface; architecture, optimizer, λ-schedule, evaluation, and
the frozen causal ablations are the unchanged frozen code path. Requires torch.

CLI: python fr_runner.py --arm O1 --seeds 18,19,20,21,22 [--steps 1200]
"""
from __future__ import annotations

import argparse
import contextlib
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
for p in (str(HERE), str(SBS), str(NEURAL)):
    if p not in sys.path:
        sys.path.insert(0, p)

SEEDS = [18, 19, 20, 21, 22]
ARMS = ["A+", "R0", "O1", "O2", "H3"]
RESULTS = HERE / "results"
SEED_DIR = RESULTS / "seeds"


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


@contextlib.contextmanager
def _swap(arm):
    """Swap exactly one frozen function for the duration of the run; always restore."""
    import interventions as IV
    import objectives as OBJ
    import curriculum_gradual as CG
    saved = {}
    try:
        if arm == "O1":
            saved["alignment_loss"] = IV.alignment_loss
            IV.alignment_loss = OBJ.correct_slot_prob_loss
        elif arm == "O2":
            saved["alignment_loss"] = IV.alignment_loss
            IV.alignment_loss = OBJ.address_margin_loss
        elif arm == "H3":
            saved["curriculum_batch"] = IV.curriculum_batch
            IV.curriculum_batch = CG.curriculum_batch_gradual
        elif arm not in ("R0", "A+"):
            raise SystemExit(f"unknown arm {arm}")
        yield
    finally:
        for k, v in saved.items():
            setattr(IV, k, v)


def env_fingerprint():
    import torch
    return {"python": sys.version.split()[0], "platform": platform.platform(),
            "machine": platform.machine(), "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(), "num_threads": torch.get_num_threads(),
            "fp": "fp32"}


def code_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO)).decode().strip()
    except Exception:
        return "unknown"


def run_arm(arm, seed, steps=1200):
    import stabilize as SB
    base = "A+" if arm == "A+" else "CR1"
    with _swap(arm):
        rec = SB.run_arm(base, seed, steps=steps)  # frozen loop; at most one function swapped
    rec["arm"] = arm
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="18,19,20,21,22")
    ap.add_argument("--arms", default="A+,R0,O1,O2,H3")
    ap.add_argument("--steps", type=int, default=1200)
    args = ap.parse_args()

    pr = subprocess.run([sys.executable, str(HERE / "verify_fr_prereg.py")], capture_output=True, text=True)
    print(pr.stdout.strip())
    if pr.returncode != 0:
        print("ABORT: functional-routing pre-registration integrity failed")
        return 2
    try:
        import torch  # noqa: F401
    except Exception:
        print("FUNCTIONAL_ROUTING_RESOURCE_BLOCKED: torch not installed.")
        return 3

    seeds = [int(s) for s in args.seeds.split(",")]
    arms = args.arms.split(",")
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RESULTS / "stage1_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {"schema": "bindingslots_functional_routing/stage1_manifest/v1",
                    "code_commit": code_commit(),
                    "frozen_reference_config_sha256": sha256_file(HERE / "frozen_reference_config.json"),
                    "objectives_sha256": sha256_file(HERE / "objectives.py"),
                    "curriculum_gradual_sha256": sha256_file(HERE / "curriculum_gradual.py"),
                    "stage1_seeds": seeds, "arms": arms, "environment": env_fingerprint(),
                    "abc_json_sha256_before": sha256_file(REPO / "experiments/phase_lc/results/abc.json"),
                    "abc_json_sha256_after": None, "restart_events": [], "seed_arm_status": {}}
    manifest["restart_events"].append({"event": "orchestrator_start", "ts_monotonic": round(time.monotonic(), 3)})
    manifest_path.write_text(json.dumps(manifest, indent=2))

    for arm in arms:
        af = SEED_DIR / f"{arm}_results.json"
        records = json.loads(af.read_text())["records"] if af.exists() else []
        done = {r["seed"] for r in records}
        for seed in seeds:
            sf = SEED_DIR / f"{arm}_seed{seed}.json"
            if sf.exists():
                if seed not in done:
                    records.append(json.loads(sf.read_text())); done.add(seed)
                continue
            t0 = time.time()
            print(f"[fr] RUN {arm} seed{seed}", flush=True)
            rec = run_arm(arm, seed, steps=args.steps)
            rec["schema"] = "bindingslots_functional_routing/seed_result/v1"
            rec["config_hash"] = sha256_file(HERE / "frozen_reference_config.json")
            rec["code_commit"] = manifest["code_commit"]
            rec["environment_fingerprint"] = manifest["environment"]
            rec["checkpoint_steps"] = [0, 60, 120, 300, 600, 900, 1200]
            sf.write_text(json.dumps(rec, indent=2))
            records.append(rec)
            manifest.setdefault("seed_arm_status", {})[f"{arm}_seed{seed}"] = "complete"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            print(f"[fr] DONE {arm} seed{seed} needle@d96={rec['needle_by_dist']['96']:.3f} "
                  f"({round(time.time()-t0,1)}s)", flush=True)
        af.write_text(json.dumps({"arm": arm, "records": sorted(records, key=lambda r: r['seed'])}, indent=2))

    manifest["abc_json_sha256_after"] = sha256_file(REPO / "experiments/phase_lc/results/abc.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("[fr] ALL ARMS COMPLETE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
