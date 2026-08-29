"""Aggregate results/*.json and evaluate the preregistered gates.

Usage: python -m experiments.phase_temporal_collector.analyze
Writes results/gates.json and prints the markdown tables for the report.

Gates: G0/G1 from PREREGISTRATION.md (unchanged); G2' and G3 from
PREREGISTRATION_AMENDMENT_2.md. The gated metric E(arm) keeps its frozen
definition: mean nMSE over the 4 forecast families x {in_dist, held_out}.
The extrap and freq_drift splits are informational only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .signals import FAMILIES, FORECAST_FAMILIES

RESULTS = Path(__file__).parent / "results"
ARMS = ["current", "stats", "harmonic", "real_rec", "phase", "osc", "raw_quad"]
SEEDS = [0, 1, 2]

# Preregistered thresholds (PREREGISTRATION.md + AMENDMENT_2)
G0_MIN_RI = 0.15
G1_MIN_RI = 0.10
G1_MIN_GAP_CLOSURE = 0.70
G1_MAX_MEM_FRAC = 0.15
G2_MIN_RI = 0.05
G3_MIN_RI = 0.05


def load():
    runs = {}
    for arm in ARMS:
        for seed in SEEDS:
            p = RESULTS / f"{arm}_seed{seed}.json"
            if p.exists():
                runs[(arm, seed)] = json.loads(p.read_text())
    return runs


def e_metric(run) -> float:
    """Frozen E(arm): mean nMSE over 4 forecast families x 2 gated splits."""
    cells = [run[split][f]["nmse"] for split in ("in_dist", "held_out")
             for f in FORECAST_FAMILIES]
    return float(np.mean(cells))


def info_metric(run, split) -> float:
    fams = [f for f in FORECAST_FAMILIES if f in run.get(split, {})]
    fams = fams or [f for f in run.get(split, {}) if f in FAMILIES]
    return float(np.mean([run[split][f]["nmse"] for f in fams])) if fams else float("nan")


def ri(ea: float, eb: float) -> float:
    return (eb - ea) / eb


def seeds_lt(per_seed, a, b):
    return sum(per_seed[a][i] < per_seed[b][i] for i in range(len(SEEDS)))


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
    g1_seeds = seeds_lt(per_seed, "harmonic", "stats")
    g1_gap = (E["stats"] - E["harmonic"]) / (E["stats"] - E["raw_quad"]) \
        if E["stats"] > E["raw_quad"] else float("nan")
    g1_mem = mem["harmonic"] / mem["raw_quad"]

    g2 = {f"ri_phase_vs_{b}": ri(E["phase"], E[b]) for b in ("harmonic", "real_rec", "osc")}
    g2.update({f"seeds_phase_lt_{b}": seeds_lt(per_seed, "phase", b)
               for b in ("harmonic", "real_rec", "osc")})
    g2["pass"] = all(g2[f"ri_phase_vs_{b}"] >= G2_MIN_RI
                     and g2[f"seeds_phase_lt_{b}"] == 3
                     for b in ("harmonic", "real_rec", "osc"))

    g3 = {f"ri_osc_vs_{b}": ri(E["osc"], E[b]) for b in ("harmonic", "real_rec")}
    g3.update({f"seeds_osc_lt_{b}": seeds_lt(per_seed, "osc", b)
               for b in ("harmonic", "real_rec")})
    g3["pass"] = all(g3[f"ri_osc_vs_{b}"] >= G3_MIN_RI
                     and g3[f"seeds_osc_lt_{b}"] == 3
                     for b in ("harmonic", "real_rec"))

    gates = {
        "G0_valid": {"ri_F_vs_B": g0, "pass": g0 >= G0_MIN_RI},
        "G1_practical": {
            "ri_C_vs_B": g1_ri, "seeds_C_lt_B": g1_seeds,
            "gap_closure": g1_gap, "mem_frac": g1_mem,
            "pass": (g1_ri >= G1_MIN_RI and g1_seeds == 3
                     and not np.isnan(g1_gap) and g1_gap >= G1_MIN_GAP_CLOSURE
                     and g1_mem <= G1_MAX_MEM_FRAC),
        },
        "G2_phase_mechanism": g2,
        "G3_oscillator_utility": g3,
        "E_per_arm": E, "E_per_seed": per_seed, "state_floats_240": mem,
    }
    (RESULTS / "gates.json").write_text(json.dumps(gates, indent=2))

    print("\n## E(arm) — mean nMSE, 4 forecast families x 2 gated splits (lower = better)\n")
    print("| Arm | E mean | per-seed | state floats @240 | params |")
    print("|---|---|---|---|---|")
    for a in ARMS:
        ps = ", ".join(f"{v:.3f}" for v in per_seed[a])
        print(f"| {a} | {E[a]:.4f} | {ps} | {mem[a]} | {runs[(a, 0)]['params']} |")

    print("\n## Per-family nMSE (seed-averaged), gated splits\n")
    print("| Arm | split | " + " | ".join(FAMILIES[:5]) + " | rare AUC |")
    print("|" + "---|" * 8)
    for a in ARMS:
        for split in ("in_dist", "held_out"):
            cells, aucs = [], []
            for f in FAMILIES[:5]:
                vals = [runs[(a, s)][split][f]["nmse"] for s in SEEDS]
                cells.append(f"{np.mean(vals):.3f}")
                if f == "rare_event":
                    aucs = [runs[(a, s)][split][f].get("auc", float("nan"))
                            for s in SEEDS]
            print(f"| {a} | {split} | " + " | ".join(cells)
                  + f" | {np.nanmean(aucs):.3f} |")

    print("\n## Informational splits (never gated)\n")
    print("| Arm | extrap forecast nMSE | freq_drift nMSE |")
    print("|---|---|---|")
    for a in ARMS:
        ex = np.mean([info_metric(runs[(a, s)], "extrap") for s in SEEDS])
        dr = np.mean([np.mean([runs[(a, s)]["freq_drift"][f]["nmse"]
                               for f in runs[(a, s)].get("freq_drift", {})
                               if f in FAMILIES])
                      for s in SEEDS
                      if runs[(a, s)].get("freq_drift")])
        print(f"| {a} | {ex:.3f} | {dr:.3f} |")

    print("\n## Gates\n")
    for k in ("G0_valid", "G1_practical", "G2_phase_mechanism", "G3_oscillator_utility"):
        print(k, json.dumps(gates[k], indent=2))


if __name__ == "__main__":
    main()
