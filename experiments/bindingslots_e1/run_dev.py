#!/usr/bin/env python3
"""Stage 2 development calibration (NON-RESERVED only): trains B0+E1 on the fixed train episodes,
evaluates on the DEV pool across dev seeds, runs the determinism fixture and the leakage suite, and
writes the dev evidence. The reserved FINAL pool and reserved seeds are never touched here."""
from __future__ import annotations

import hashlib
import json
import pathlib

import config as C
import harness as H
import leakage as L

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def main():
    # --- determinism fixture: run one dev seed twice, require byte-identical ---
    a = H.run_seed(C.DEV_SEEDS[0], "dev")
    b = H.run_seed(C.DEV_SEEDS[0], "dev")
    det = {
        "seed": C.DEV_SEEDS[0],
        "e1_hash_match": a["e1_param_sha256"] == b["e1_param_sha256"],
        "b0_hash_match": a["b0_param_sha256"] == b["b0_param_sha256"],
        "metrics_match": a["metrics"] == b["metrics"],
        "e1_param_sha256": a["e1_param_sha256"], "b0_param_sha256": a["b0_param_sha256"],
    }
    det["determinism_ok"] = det["e1_hash_match"] and det["b0_hash_match"] and det["metrics_match"]
    _write("determinism.json", {"schema": "bindingslots_e1/determinism/v1", **det})

    # --- leakage suite on dev eval splits ---
    dev_splits = H.eval_splits_for("dev", C.DEV_SEED_BASE)
    lk = L.run_all(dev_splits)
    _write("leakage_report.json", {"schema": "bindingslots_e1/leakage/v1", **lk})

    # --- per-dev-seed gate evaluation ---
    per_seed = [a] + [H.run_seed(s, "dev") for s in C.DEV_SEEDS[1:]]
    summary = []
    for r in per_seed:
        m, g = r["metrics"], r["gates"]
        summary.append({"seed": r["seed"], "all_primary_pass": g["all_primary_pass"],
                        "groups": g["groups"],
                        "G1_addr": round(m["G1_addr"], 3), "G1_e2e": round(m["G1_e2e"], 3),
                        "b0_G1_e2e": round(m["b0_G1_e2e"], 3),
                        "improvement_over_b0": round(m["improvement_over_b0"], 3),
                        "nomatch_false_accept": round(m["nomatch_false_accept"], 3),
                        "nomatch_recall": round(m["nomatch_recall"], 3),
                        "nomatch_precision": round(m["nomatch_precision"], 3),
                        "G7_addr": round(m["G7_addr"], 3)})
    n_pass = sum(1 for s in summary if s["all_primary_pass"])
    _write("dev_calibration.json", {
        "schema": "bindingslots_e1/dev_calibration/v1",
        "config": {k: getattr(C, k) for k in ("D", "STEPS", "BATCH", "LR", "TAU",
                   "TRAIN_EPISODES", "TRAIN_NO_MATCH_FRAC")},
        "gates": C.GATES, "dev_seeds": C.DEV_SEEDS,
        "per_seed": [{"seed": r["seed"], "metrics": r["metrics"], "gates": r["gates"],
                      "e1_splits": r["e1_splits"], "b0_splits": r["b0_splits"]} for r in per_seed],
        "dev_seeds_passing_all_primary": n_pass})

    print("=== DEV CALIBRATION ===", flush=True)
    print("determinism_ok:", det["determinism_ok"], "| leakage all_pass:", lk["all_pass"], flush=True)
    for s in summary:
        print(s, flush=True)
    print(f"dev seeds passing all primary gates: {n_pass}/{len(summary)}", flush=True)


if __name__ == "__main__":
    main()
