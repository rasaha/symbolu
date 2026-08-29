"""Aggregate results/*.json and evaluate the preregistered gates G0-G2.

Usage: python -m experiments.phase_temporal_collector.analyze
Writes results/gates.json and prints the markdown tables for the report.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .signals import FAMILIES, FORECAST_FAMILIES

RESULTS = Path(__file__).parent / "results"
ARMS = ["current", "stats", "harmonic", "real_rec", "phase", "raw_quad"]
SEEDS = [0, 1, 2]

# Preregistered thresholds (PREREGISTRATION.md)
G0_MIN_RI = 0.15
G1_MIN_RI = 0.10
G1_MIN_GAP_CLOSURE = 0.70
G1_MAX_MEM_FRAC = 0.15
G2_MIN_RI = 0.05


def load():
    runs = {}
    for arm in ARMS:
        for seed in SEEDS:
            p = RESULTS / f"{arm}_seed{seed}.json"
            if p.exists():
                runs[(arm, seed)] = json.loads(p.read_text())
    return runs


def e_metric(run) -> float:
    """Preregistered E(arm): mean nMSE over 4 forecast families x 2 splits."""
    cells = [run[split][f]["nmse"] for split in ("in_dist", "held_out")
             for f in FORECAST_FAMILIES]
    return float(np.mean(cells))


def ri(ea: float, eb: float) -> float:
    return (eb - ea) / eb


def main():
    runs = load()
    missing = [(a, s) for a in ARMS for s in SEEDS if (a, s) not in runs]
    if missing:
        print("MISSING RUNS:", missing)
        return

    per_seed = {a: [e_metric(runs[(a, s)]) for s in SEEDS] for a in ARMS}
    E = {a: float(np.mean(v)) for a, v in per_seed.items()}
    mem = {a: runs[(a, 0)]["state_floats_at_240"] for a in ARMS}

    g0 = ri(E["raw_quad"], E["stats"])
    g1_ri = ri(E["harmonic"], E["stats"])
    g1_seeds = sum(per_seed["harmonic"][i] < per_seed["stats"][i] for i in range(3))
    g1_gap = (E["stats"] - E["harmonic"]) / (E["stats"] - E["raw_quad"]) \
        if E["stats"] > E["raw_quad"] else float("nan")
    g1_mem = mem["harmonic"] / mem["raw_quad"]
    g2_ri_c = ri(E["phase"], E["harmonic"])
    g2_ri_d = ri(E["phase"], E["real_rec"])
    g2_seeds_c = sum(per_seed["phase"][i] < per_seed["harmonic"][i] for i in range(3))
    g2_seeds_d = sum(per_seed["phase"][i] < per_seed["real_rec"][i] for i in range(3))

    gates = {
        "G0_valid": {"ri_F_vs_B": g0, "pass": g0 >= G0_MIN_RI},
        "G1_practical": {
            "ri_C_vs_B": g1_ri, "seeds_C_lt_B": g1_seeds,
            "gap_closure": g1_gap, "mem_frac": g1_mem,
            "pass": (g1_ri >= G1_MIN_RI and g1_seeds == 3
                     and g1_gap >= G1_MIN_GAP_CLOSURE
                     and g1_mem <= G1_MAX_MEM_FRAC),
        },
        "G2_phase_mechanism": {
            "ri_E_vs_C": g2_ri_c, "ri_E_vs_D": g2_ri_d,
            "seeds_E_lt_C": g2_seeds_c, "seeds_E_lt_D": g2_seeds_d,
            "pass": (g2_ri_c >= G2_MIN_RI and g2_ri_d >= G2_MIN_RI
                     and g2_seeds_c == 3 and g2_seeds_d == 3),
        },
        "E_per_arm": E, "E_per_seed": per_seed, "state_floats_240": mem,
    }
    (RESULTS / "gates.json").write_text(json.dumps(gates, indent=2))

    print("\n## E(arm) — mean nMSE, 4 forecast families x 2 splits (lower = better)\n")
    print("| Arm | E mean | per-seed | state floats @240 | params |")
    print("|---|---|---|---|---|")
    for a in ARMS:
        ps = ", ".join(f"{v:.3f}" for v in per_seed[a])
        print(f"| {a} | {E[a]:.4f} | {ps} | {mem[a]} | {runs[(a, 0)]['params']} |")

    print("\n## Per-family nMSE (seed-averaged)\n")
    hdr = "| Arm | split | " + " | ".join(FAMILIES) + " | rare AUC |"
    print(hdr)
    print("|" + "---|" * (len(FAMILIES) + 3))
    for a in ARMS:
        for split in ("in_dist", "held_out"):
            cells, aucs = [], []
            for f in FAMILIES:
                vals = [runs[(a, s)][split][f]["nmse"] for s in SEEDS]
                cells.append(f"{np.mean(vals):.3f}")
                if f == "rare_event":
                    aucs = [runs[(a, s)][split][f].get("auc", float("nan"))
                            for s in SEEDS]
            print(f"| {a} | {split} | " + " | ".join(cells)
                  + f" | {np.nanmean(aucs):.3f} |")

    print("\n## Gates\n")
    for k in ("G0_valid", "G1_practical", "G2_phase_mechanism"):
        print(k, json.dumps(gates[k], indent=2))


if __name__ == "__main__":
    main()
