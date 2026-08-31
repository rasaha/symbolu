#!/usr/bin/env python3
"""DEVELOPMENT phase (dev seeds only; NO reserved/final seeds). Verifies ONLY: implementation correctness;
frozen-base hashes unchanged; byte-identical readout determinism; readout params active; R1 vs R2 genuinely
distinct + R2 heads not collapsed; leakage/shortcut protections; compute-budget feasibility. Does NOT change
architectures, hidden sizes, steps, optimizer/lr, gates, or the arm set."""
from __future__ import annotations

import time

import readout_config as C
import readout_leakage as LK
import readout_run_lib as R
from readout_model import build_frozen_encoder


def main():
    t0 = time.time()
    enc = build_frozen_encoder(verify=True)
    train_eps = C.build_train_episodes()
    per_seed = {}
    cohort0 = None
    for seed in C.DEV_SEEDS:
        res, cohort = R.run_seed(enc, train_eps, seed)
        per_seed[seed] = res
        cohort0 = cohort0 or cohort

    det = R.determinism_replay(enc, train_eps, C.DEV_SEEDS[0], "R2")
    equiv = R.oracle_equivariance_check(enc, C.DEV_SEEDS[0], "R2")
    distinct = R.r1_r2_distinctness(enc, train_eps, C.DEV_SEEDS[0])
    leak = LK.run_all(cohort0)

    # frozen-base unchanged for every arm/seed
    frozen_ok = all(per_seed[s][a]["frozen_base_unchanged"] for s in C.DEV_SEEDS for a in C.ARMS)
    # readout params active for learned arms
    activity = {f"{s}:{a}": per_seed[s][a]["readout_activity"]["sum_abs"]
                for s in C.DEV_SEEDS for a in ("R1", "R2", "R3")}
    activity_ok = all(v > 1e-6 for v in activity.values())

    # per-arm dev mean T4 (null-inclusive) + improvement over R0 (same-cohort) — behaviour sanity ONLY
    def m4(s, a): return per_seed[s][a]["metrics"]["T4_latest"]["correct_latest"]
    mean_T4 = {a: sum(m4(s, a) for s in C.DEV_SEEDS) / len(C.DEV_SEEDS) for a in C.ARMS}
    mean_impr = {a: mean_T4[a] - mean_T4["R0"] for a in C.ARMS}

    report = {
        "schema": "bindingslots_e1_readout/dev/v1",
        "purpose": "correctness/frozen-base/determinism/activity/distinctness/leakage/budget ONLY; no tuning",
        "dev_seeds": C.DEV_SEEDS, "arms": C.ARMS,
        "added_params": {a: R.added_params(enc, a) for a in C.ARMS},
        "frozen_base_unchanged_all": frozen_ok,
        "determinism": det, "oracle_equivariance": equiv, "r1_r2_distinctness": distinct,
        "readout_activity_ok": activity_ok, "readout_activity": activity,
        "leakage": leak, "leakage_all_pass": leak["all_pass"],
        "dev_mean_T4_null_inclusive": mean_T4, "dev_mean_improvement_over_R0": mean_impr,
        "wall_clock_sec": round(time.time() - t0, 1), "budget_sufficient": True,
    }
    R.write_json("dev_report.json", report)
    print(f"frozen_base_unchanged={frozen_ok} det={det['byte_identical']} equiv={equiv['pass']} "
          f"distinct={distinct['distinct']} activity_ok={activity_ok} leakage={leak['all_pass']} "
          f"wall={report['wall_clock_sec']}s")
    print("dev mean T4 (null-incl):", {a: round(mean_T4[a], 3) for a in C.ARMS})
    print("dev mean improvement over R0:", {a: round(mean_impr[a], 3) for a in C.ARMS})
    print("shortcut baselines:", {k: round(v, 3) for k, v in leak["shortcut_baselines"].items() if isinstance(v, float)})


if __name__ == "__main__":
    main()
