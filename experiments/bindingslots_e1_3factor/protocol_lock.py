#!/usr/bin/env python3
"""Protocol lock for the three-factor factorial. Freezes — BEFORE any final/reserved seed runs — the given
gate numbers, the fresh disjoint seed set, the per-cell added-parameter counts, and the sha256 of every
factor/harness source file, so it is provable that the factor implementations were NOT tuned on dev
results between the development phase and the final phase. Fails closed if any final artifact already
exists (a final seed must never precede the lock)."""
from __future__ import annotations

import hashlib
import json
import pathlib

import factor_config as C
import run_lib as R

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"
FROZEN_SOURCES = ["factor_model.py", "factor_config.py", "factor_train.py", "factor_eval.py",
                  "factor_gates.py", "factor_leakage.py", "run_lib.py"]
FINAL_ARTIFACTS = ["final_per_seed.json", "final_report.json", "factorial_analysis.json"]


def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    # (a) no final artifact may exist yet
    existing = [n for n in FINAL_ARTIFACTS if (RES / n).exists()]
    assert not existing, f"final artifacts already present before lock: {existing}"

    # (b) seeds disjoint from every prior seed in the program
    prior = C.all_prior_seeds()
    prop = C.proposed_seeds()
    clash = sorted(prior & prop)
    assert not clash, f"seed collision with prior: {clash}"

    # (c) dev integrity must have passed (correctness/determinism/activity/leakage/budget)
    dev = json.loads((RES / "dev_report.json").read_text())
    dev_ok = (dev["determinism"]["byte_identical"] and dev["oracle_equivariance"]["pass"]
              and dev["factor_activity_ok"] and dev["leakage_all_pass"] and dev["budget_sufficient"])
    assert dev_ok, "dev-phase integrity did not pass; do not lock"

    lock = {
        "schema": "bindingslots_e1_3factor/protocol_lock/v1",
        "locked_before": "first final/reserved seed",
        "cells": list(C.CELLS.keys()),
        "factors_per_cell": {c: list(f) for c, f in C.CELLS.items()},
        "added_params_per_cell": {c: R.added_params_for(c) for c in C.CELLS},
        "base_recipe": {"D": C.D, "STEPS": C.STEPS, "TAU": C.TAU, "BATCH": C.BATCH, "LR": C.LR,
                        "TRAIN_EPISODES": C.TRAIN_EPISODES, "TRAIN_NO_MATCH_FRAC": C.TRAIN_NO_MATCH_FRAC},
        "seeds": {"train": C.TRAIN_SEED, "dev": C.DEV_SEEDS, "final": C.FINAL_SEEDS,
                  "required_seeds_pass": C.REQUIRED_TO_PASS, "eval_n_per_split": C.EVAL_N_PER_SPLIT},
        "seed_disjoint_from_prior": True, "prior_seed_count": len(prior),
        "gates": C.GATES,
        "metric_conventions": {
            "T4_gated": "null-inclusive correct_latest = P(argmax over K+1 == target index)",
            "inherited_splits_gated": "null-excluded addressing_top1 = P(argmax over real keys == target)",
            "T4_improvement_baseline": "cell 000 mean T4 (null-inclusive)",
            "T5": "reported diagnostic only; excluded from gates, selection, and verdict",
        },
        "selection_rule": ["fewest enabled factors", "lowest added parameter count",
                           "highest worst-seed T4", "highest mean T4"],
        "verdict_vocabulary": ["T4_FACTORIAL_SINGLE_FACTOR_SELECTED", "T4_FACTORIAL_COMBINATION_SELECTED",
                               "T4_FACTORIAL_ALL_FACTORS_REQUIRED", "T4_FACTORIAL_NO_INTERVENTION_SELECTED",
                               "T4_FACTORIAL_PROTOCOL_VIOLATED", "T4_FACTORIAL_RESOURCE_BLOCKED"],
        "always_preserve": C.PRESERVE,
        "never_emit": ["E1_TEMPORAL_TRANSFER_VALIDATED", "E1_STRUCTURAL_TRANSFER_CONFIRMED",
                       "any KDA-unblocking verdict"],
        "frozen_source_sha256": {n: sha256_file(HERE / n) for n in FROZEN_SOURCES},
        "dev_integrity": {"determinism_byte_identical": dev["determinism"]["byte_identical"],
                          "oracle_equivariance": dev["oracle_equivariance"]["pass"],
                          "factor_activity_ok": dev["factor_activity_ok"],
                          "leakage_all_pass": dev["leakage_all_pass"],
                          "dev_wall_clock_sec": dev["wall_clock_sec"]},
    }
    p = R.write_json("protocol_lock.json", lock)
    print("PROTOCOL LOCKED ->", p)
    print("seeds disjoint:", not clash, "| gates T4>=", C.GATES["T4_min"],
          "impr>=", C.GATES["T4_improvement_over_000_min"], "| required", C.REQUIRED_TO_PASS, "of 5")
    print("added params/cell:", lock["added_params_per_cell"])


if __name__ == "__main__":
    main()
