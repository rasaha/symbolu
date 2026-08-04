#!/usr/bin/env python3
"""Authorized adaptive persistence execution driver.

The ONLY execution-order authority is adaptive_plan.next_action(...). This driver: verifies the
authorization + frozen hashes, resumes from the persisted evidence, asks the planner for exactly one
next (arm, seed), runs it to step 1200 via the frozen arm implementations, classifies it from evidence
with the frozen classifier (same-seed A+), persists atomically, and repeats until the planner returns a
terminal decision. It contains NO decision tree of its own and never pre-queues the matrix.

Requires torch. Run: python execute_adaptive.py   (resumable / idempotent)
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import adaptive_plan as AP  # noqa: E402  (only order authority)
import persistence_classify as PC  # noqa: E402

RESULTS = HERE / "results"
SEEDS_ROOT = RESULTS / "seeds"
LEDGER = RESULTS / "execution_ledger.json"
PLAN = json.loads((HERE / "adaptive_execution_plan.json").read_text())


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def code_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO)).decode().strip()
    except Exception:
        return "unknown"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def verify_frozen():
    for rel, want in PLAN["frozen_source_hashes_sha256"].items():
        if sha256_file(HERE / rel) != want:
            raise SystemExit(f"PERSISTENCE_PROTOCOL_VIOLATED: frozen file changed: {rel}")
    auth = HERE / "execution_authorization.json"
    if not auth.exists():
        raise SystemExit("PERSISTENCE_PROTOCOL_VIOLATED: no execution_authorization.json")
    a = json.loads(auth.read_text())
    if a["pr_1332_merge_commit"] != "101951cb8bbccca32b6e3faa371bc675371dca89":
        raise SystemExit("PERSISTENCE_PROTOCOL_VIOLATED: authorization does not reference the merged amendment")


def seed_dir(arm, seed):
    return SEEDS_ROOT / arm / f"seed_{seed}"


def raw_path(arm, seed):
    return seed_dir(arm, seed) / "raw_record.json"


def load_raw(arm, seed):
    p = raw_path(arm, seed)
    return json.loads(p.read_text()) if p.exists() else None


def completed_from_evidence():
    """Reconstruct the ordered completed list from the persisted ledger, RECLASSIFYING each seed from
    its raw evidence + same-seed A+ (never trusting a stored boolean)."""
    if not LEDGER.exists():
        return []
    order = json.loads(LEDGER.read_text())["order"]
    out = []
    for e in order:
        arm, seed = e["arm"], e["seed"]
        rec = load_raw(arm, seed)
        if rec is None:
            raise SystemExit(f"PERSISTENCE_INTEGRITY_FAILED: missing raw evidence for {arm} seed{seed}")
        if arm == "A+":
            cs = False  # A+ control is never a candidate; planner ignores its clean_stable
        else:
            ap = load_raw("A+", seed)
            if ap is None:
                raise SystemExit(f"PERSISTENCE_INTEGRITY_FAILED: missing same-seed A+ for {arm} seed{seed}")
            cs = PC.classify_seed(rec, ap)["clean_stable"]
        out.append({"arm": arm, "seed": seed, "clean_stable": cs})
    return out


def persist_seed(arm, seed, rec, order_index, cc):
    d = seed_dir(arm, seed)
    d.mkdir(parents=True, exist_ok=True)
    atomic_write(raw_path(arm, seed), json.dumps(rec, indent=2))
    classification = None
    if arm != "A+":
        ap = load_raw("A+", seed)
        classification = PC.classify_seed(rec, ap)
    env = json.loads((HERE / "execution_authorization.json").read_text())["environment"]
    manifest = {
        "schema": "bindingslots_persistence/run_manifest/v1", "arm": arm, "seed": seed,
        "execution_order": order_index, "source_commit": cc, "execution_code_commit": cc,
        "frozen_config_digest": sha256_file(HERE / "frozen_reference_config.json"),
        "adaptive_plan_digest": sha256_file(HERE / "adaptive_execution_plan.json"),
        "classifier_digest": sha256_file(HERE / "classifier.json"),
        "environment": env, "device": "cpu", "restart_count": rec.get("restart_count", 0),
        "params": rec.get("params"), "train_s": rec.get("train_s"),
        "artifact_hash": sha256_file(raw_path(arm, seed)),
    }
    atomic_write(d / "run_manifest.json", json.dumps(manifest, indent=2))
    # curated per-checkpoint metrics + routing trajectory
    traj = rec.get("trajectory", [])
    cm = [{"step": t["step"], "needle_d96": t.get("needle_d96"),
           "routing": {k: (t.get("routing", {}) or {}).get(k) for k in
                       ("read_prob_on_highest_write_slot", "rank_of_highest_write_slot_under_read",
                        "address_logit_margin", "write_read_overlap", "read_entropy", "write_entropy")}}
          for t in traj]
    atomic_write(d / "checkpoint_metrics.json", json.dumps({"schema": "bindingslots_persistence/checkpoint_metrics/v1",
                 "arm": arm, "seed": seed, "checkpoints": cm}, indent=2))
    atomic_write(d / "routing_trajectory.json", json.dumps({"schema": "bindingslots_persistence/routing_trajectory/v1",
                 "arm": arm, "seed": seed, "checkpoints": traj}, indent=2))
    atomic_write(d / "causal_ablation_result.json", json.dumps({"schema": "bindingslots_persistence/causal_ablation_result/v1",
                 "arm": arm, "seed": seed, "step": 1200, "ablation": rec.get("ablation", {}),
                 "aplus_same_seed_d96": (classification or {}).get("aplus_needle_d96_1200")}, indent=2))
    if classification is not None:
        atomic_write(d / "seed_classification.json", json.dumps({"schema": "bindingslots_persistence/seed_classification/v1",
                     "arm": arm, "seed": seed, **classification}, indent=2))
    atomic_write(d / "integrity_record.json", json.dumps({"schema": "bindingslots_persistence/integrity_record/v1",
                 "arm": arm, "seed": seed, "raw_record_sha256": sha256_file(raw_path(arm, seed)),
                 "code_commit": cc}, indent=2))
    return classification


def append_ledger(arm, seed, cs, category):
    order = json.loads(LEDGER.read_text())["order"] if LEDGER.exists() else []
    order.append({"arm": arm, "seed": seed, "clean_stable": cs, "category": category,
                  "dir": str(seed_dir(arm, seed).relative_to(HERE))})
    atomic_write(LEDGER, json.dumps({"schema": "bindingslots_persistence/execution_ledger/v1", "order": order}, indent=2))


def main():
    verify_frozen()
    try:
        import torch  # noqa: F401
    except Exception:
        print("PERSISTENCE_RESOURCE_BLOCKED: torch not installed.")
        return 3
    import persistence_arms as ARMS

    cc = code_commit()
    while True:
        completed = completed_from_evidence()
        act = AP.next_action(completed)
        if act["action"] == "terminate":
            print(f"[exec] TERMINAL: {act['verdict']} selected={act.get('selected')}", flush=True)
            (RESULTS).mkdir(exist_ok=True)
            atomic_write(RESULTS / "terminal_decision.json", json.dumps(act, indent=2))
            return 0
        arm, seed = act["arm"], act["seed"]
        # idempotent: if raw evidence already exists, skip re-run (resume)
        if load_raw(arm, seed) is not None:
            # ensure ledger has it
            order = json.loads(LEDGER.read_text())["order"] if LEDGER.exists() else []
            if not any(e["arm"] == arm and e["seed"] == seed for e in order):
                rec = load_raw(arm, seed)
                cls = PC.classify_seed(rec, load_raw("A+", seed)) if arm != "A+" else None
                append_ledger(arm, seed, (cls or {}).get("clean_stable", False), (cls or {}).get("category", "REFERENCE"))
            continue
        t0 = time.time()
        print(f"[exec] RUN {arm} seed{seed} (order {len(completed)})", flush=True)
        rec = ARMS.run_arm(arm, seed, steps=1200)
        rec["arm"] = arm
        cls = persist_seed(arm, seed, rec, len(completed), cc)
        cs = (cls or {}).get("clean_stable", False)
        category = (cls or {}).get("category", "REFERENCE" if arm == "A+" else "UNKNOWN")
        append_ledger(arm, seed, cs, category)
        print(f"[exec] DONE {arm} seed{seed} needle@d96={rec['needle_by_dist']['96']:.3f} "
              f"clean_stable={cs} cat={category} ({round(time.time()-t0,1)}s)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
