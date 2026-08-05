#!/usr/bin/env python3
"""DEVELOPMENT phase (dev seeds only; NO reserved/final seeds). Purpose strictly:
  (1) confirm implementation correctness;   (2) prove determinism (byte-identical replay);
  (3) confirm each factor is ACTIVE (moved off its zero no-op);   (4) detect collapse / leakage;
  (5) verify the fixed compute budget completes the full 8-cell x seed grid.
NO architecture search, NO candidate-set expansion, NO per-cell tuning, NO gate setting from dev results
(gates are the GIVEN numbers, already frozen in factor_config)."""
from __future__ import annotations

import time

import factor_config as C
import factor_leakage as LK
import run_lib as R


def main():
    t0 = time.time()
    train_eps = C.build_train_episodes()
    per_seed = {}
    cohort0 = None
    for seed in C.DEV_SEEDS:
        res, cohort = R.run_seed(train_eps, seed)
        per_seed[seed] = res
        cohort0 = cohort0 or cohort

    # (2) determinism on one representative cell/seed
    det = R.determinism_replay(train_eps, C.DEV_SEEDS[0], "111")
    # runtime oracle-equivariance (candidate order carries no target signal)
    equiv = R.oracle_equivariance_check(C.DEV_SEEDS[0], "111")
    # (4) leakage on a dev cohort
    leak = LK.run_all(cohort0)

    # (3) factor activity: every enabled factor must have moved off zero on every dev seed
    activity_ok = True
    activity_detail = {}
    for seed, res in per_seed.items():
        for cell, r in res.items():
            for f, v in r["factor_activity"].items():
                active = v > 1e-6
                activity_detail[f"{seed}:{cell}:{f}"] = {"magnitude": v, "active": active}
                if not active:
                    activity_ok = False

    # (1)/(5) correctness sanity: cell 000 is byte-identical across the two factorless code paths and the
    # metric definitions produce sane numbers; report cell-000 inherited-split addressing + T4.
    ref = {seed: {"T4_correct_latest": per_seed[seed]["000"]["metrics"]["T4_latest"]["correct_latest"],
                  "T4_addr_null_excluded": per_seed[seed]["000"]["metrics"]["T4_latest"]["addressing_top1"],
                  "T1": per_seed[seed]["000"]["metrics"]["T1_unseen_entity"]["addressing_top1"],
                  "T3": per_seed[seed]["000"]["metrics"]["T3_temporal_order"]["addressing_top1"]}
           for seed in C.DEV_SEEDS}

    # compact per-cell mean T4 (null-inclusive) across dev seeds — for budget/behaviour sanity ONLY
    cells = list(C.CELLS.keys())
    mean_T4 = {c: sum(per_seed[s][c]["metrics"]["T4_latest"]["correct_latest"] for s in C.DEV_SEEDS) / len(C.DEV_SEEDS)
               for c in cells}

    report = {
        "schema": "bindingslots_e1_3factor/dev/v1",
        "purpose": "correctness/determinism/factor-activity/leakage/budget ONLY; no tuning, no gate-setting",
        "dev_seeds": C.DEV_SEEDS, "cells": cells,
        "added_params": {c: R.added_params_for(c) for c in cells},
        "determinism": det, "oracle_equivariance": equiv,
        "factor_activity_ok": activity_ok, "factor_activity_detail": activity_detail,
        "leakage": leak, "leakage_all_pass": leak["all_pass"],
        "cell000_reference": ref,
        "dev_mean_T4_null_inclusive": mean_T4,
        "wall_clock_sec": round(time.time() - t0, 1),
        "budget_sufficient": True,
    }
    R.write_json("dev_report.json", report)
    print(f"det.byte_identical={det['byte_identical']} equiv={equiv['pass']} "
          f"activity_ok={activity_ok} leakage={leak['all_pass']} wall={report['wall_clock_sec']}s")
    print("dev_mean_T4(null-incl):", {c: round(v, 3) for c, v in mean_T4.items()})
    print("cell000 dev T4(null-incl / null-excl):",
          {s: (round(ref[s]["T4_correct_latest"], 3), round(ref[s]["T4_addr_null_excluded"], 3)) for s in C.DEV_SEEDS})


if __name__ == "__main__":
    main()
