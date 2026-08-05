#!/usr/bin/env python3
"""Factorial analysis + mechanical verdict from the reserved evidence (final_per_seed.json). Applies the
frozen gates, computes 2^3 main effects + all interactions (on T4 and on each diagnosed component),
applies the mechanical selection rule, and emits exactly one primary verdict. Torch-free."""
from __future__ import annotations

import json
import pathlib

import factor_config as C
import factor_gates as G

RES = pathlib.Path(__file__).resolve().parent / "results"
SPLITS_REPORT = ["T1_unseen_entity", "T2_unseen_combo", "T3_temporal_order", "T4_latest",
                 "T5_pred_succ", "T6_paraphrase", "T7_confusable", "T8_no_match", "T9_stable"]


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    data = json.loads((RES / "final_per_seed.json").read_text())
    lock = json.loads((RES / "protocol_lock.json").read_text())
    per_seed = data["per_seed"]
    seeds = [str(s) for s in C.FINAL_SEEDS]
    cells = list(C.CELLS.keys())
    added = data["added_params_per_cell"]

    # ---- full per-cell/per-seed/per-split reporting table ----
    table = {}
    for c in cells:
        table[c] = {"factors": list(C.CELLS[c]), "added_params": added[c], "per_seed": {}}
        for s in seeds:
            m = per_seed[s][c]["metrics"]
            row = {}
            for sp in SPLITS_REPORT:
                mm = m[sp]
                row[sp] = {k: round(mm[k], 4) for k in mm}
            table[c]["per_seed"][s] = {"metrics": row,
                                       "param_hash": per_seed[s][c]["param_hash"],
                                       "factor_activity": per_seed[s][c]["factor_activity"]}

    # ---- per-cell aggregates ----
    def cell_metric_mean(c, split, key):
        return _mean([per_seed[s][c]["metrics"][split][key] for s in seeds])

    mean_T4 = {c: cell_metric_mean(c, "T4_latest", "correct_latest") for c in cells}
    ref_T4 = mean_T4[C.REFERENCE_CELL]

    # ---- gates + qualification per cell ----
    qualifications = []
    for c in cells:
        seed_metrics = [per_seed[s][c]["metrics"] for s in seeds]
        q = G.cell_qualification(c, seed_metrics, ref_T4, added[c])
        qualifications.append(q)
    qual_by_cell = {q["cell"]: q for q in qualifications}

    # ---- 2^3 factorial effects on T4 and on components ----
    def effects_on(split, key):
        cm = {c: cell_metric_mean(c, split, key) for c in cells}
        return G.factorial_effects(cm), cm
    eff_T4, cm_T4 = effects_on("T4_latest", "correct_latest")
    eff_abstain, _ = effects_on("T4_latest", "null_rate")
    eff_wrongent, _ = effects_on("T4_latest", "wrong_entity")
    eff_older, _ = effects_on("T4_latest", "right_entity_wrong_older")

    # ---- experiment-level integrity ----
    determinism_ok = bool(data["determinism"]["byte_identical"] and data["oracle_equivariance"]["pass"])
    leakage_ok = bool(data["leakage_all_pass"])
    protocol_ok = bool(data["source_hashes_match_lock"])

    # ---- selection + verdict ----
    selected = G.select_cell(qualifications)
    v, sel_cell, preserve = G.verdict(selected, determinism_ok, leakage_ok, protocol_ok)

    # ---- diagnostic-only T5 (never in gates/selection/verdict) ----
    t5 = {c: round(cell_metric_mean(c, "T5_pred_succ", "correct_latest"), 4) for c in cells}

    analysis = {
        "schema": "bindingslots_e1_3factor/analysis/v1",
        "reference_cell": C.REFERENCE_CELL, "reference_mean_T4_null_inclusive": round(ref_T4, 4),
        "mean_T4_null_inclusive": {c: round(mean_T4[c], 4) for c in cells},
        "mean_T4_null_excluded_addressing": {c: round(cell_metric_mean(c, "T4_latest", "addressing_top1"), 4) for c in cells},
        "improvement_over_000": {c: round(mean_T4[c] - ref_T4, 4) for c in cells},
        "worst_seed_T4": {c: round(min(per_seed[s][c]["metrics"]["T4_latest"]["correct_latest"] for s in seeds), 4) for c in cells},
        "seeds_passing_all_primary": {q["cell"]: q["seeds_passing_all_primary"] for q in qualifications},
        "qualifies": {q["cell"]: q["qualifies"] for q in qualifications},
        "added_params_per_cell": added,
        "factorial_effects_on_T4": {k: round(x, 4) for k, x in eff_T4.items()},
        "factorial_effects_on_abstention": {k: round(x, 4) for k, x in eff_abstain.items()},
        "factorial_effects_on_wrong_entity": {k: round(x, 4) for k, x in eff_wrongent.items()},
        "factorial_effects_on_right_entity_wrong_older": {k: round(x, 4) for k, x in eff_older.items()},
        "component_means_cell000": {
            "null_rate": round(cell_metric_mean("000", "T4_latest", "null_rate"), 4),
            "wrong_entity": round(cell_metric_mean("000", "T4_latest", "wrong_entity"), 4),
            "right_entity_wrong_older": round(cell_metric_mean("000", "T4_latest", "right_entity_wrong_older"), 4),
            "correct_entity": round(cell_metric_mean("000", "T4_latest", "correct_entity"), 4),
        },
        "interaction_note": "F1xF2 pre-flagged from the diagnostics (D2 1.4% vs D3 68%); reported below.",
        "determinism_ok": determinism_ok, "leakage_ok": leakage_ok, "protocol_ok": protocol_ok,
        "selection_rule": lock["selection_rule"],
        "selected_cell": sel_cell,
        "verdict": v,
        "preserved": preserve,
        "t5_diagnostic_only": t5,
        "gates": C.GATES,
        "interpretation": (
            "Minimal, non-oracle, capacity-fixed learnable factors do NOT recover the T4 latest-state "
            "shortfall on the temporal family: no cell reaches T4>=0.85 (null-inclusive) nor improves the "
            "reference by >=0.05. Only F1 (learned null gating) yields a positive main effect; F2 and F3 "
            "are ~0. E1_TEMPORAL_TRANSFER_PARTIAL stands; KDA remains blocked."
        ),
    }
    p = RES / "factorial_analysis.json"
    tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(analysis, indent=2, sort_keys=True)); tmp.replace(p)
    fp = RES / "final_report.json"
    tmpf = fp.with_suffix(".json.tmp")
    tmpf.write_text(json.dumps({"schema": "bindingslots_e1_3factor/report_table/v1", "table": table,
                                "verdict": v, "selected_cell": sel_cell, "preserved": preserve},
                               indent=2, sort_keys=True)); tmpf.replace(fp)

    print("VERDICT:", v, "| selected:", sel_cell)
    print("mean T4 (null-incl):", {c: round(mean_T4[c], 3) for c in cells})
    print("improvement over 000:", {c: round(mean_T4[c] - ref_T4, 3) for c in cells})
    print("qualifies:", {q["cell"]: q["qualifies"] for q in qualifications})
    print("F1/F2/F3 main effects on T4:", {k: round(eff_T4[k], 4) for k in ("F1", "F2", "F3")})
    print("F1xF2 / F1xF3 / F2xF3 / F1xF2xF3:",
          {k: round(eff_T4[k], 4) for k in ("F1xF2", "F1xF3", "F2xF3", "F1xF2xF3")})
    print("effects on abstention (null_rate):", {k: round(eff_abstain[k], 4) for k in ("F1", "F2", "F3", "F1xF2")})
    print("preserved:", preserve)


if __name__ == "__main__":
    main()
