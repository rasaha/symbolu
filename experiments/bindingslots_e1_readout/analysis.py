#!/usr/bin/env python3
"""Readout-diagnostic analysis + mechanical conclusion from the reserved evidence (final_per_seed.json).
Applies the frozen gates, evaluates each arm, selects among tied learned arms, and emits exactly one
diagnostic conclusion. Torch-free."""
from __future__ import annotations

import json
import pathlib

import readout_config as C
import readout_gates as G

RES = pathlib.Path(__file__).resolve().parent / "results"
SPLITS_REPORT = ["T1_unseen_entity", "T2_unseen_combo", "T3_temporal_order", "T4_latest",
                 "T5_pred_succ", "T6_paraphrase", "T7_confusable", "T8_no_match", "T9_stable"]


def main():
    data = json.loads((RES / "final_per_seed.json").read_text())
    lock = json.loads((RES / "protocol_lock.json").read_text())
    per_seed = data["per_seed"]
    seeds = [str(s) for s in C.FINAL_SEEDS]
    added = data["added_params_per_arm"]

    def cm(a, s): return per_seed[s][a]["metrics"]
    r0_seed_T4 = [cm("R0", s)["T4_latest"]["correct_latest"] for s in seeds]

    # full per-arm/seed/split reporting table
    table = {}
    for a in C.ARMS:
        table[a] = {"added_params": added[a], "head_param_breakdown": per_seed[seeds[0]][a]["head_param_breakdown"],
                    "per_seed": {}}
        for s in seeds:
            m = cm(a, s)
            table[a]["per_seed"][s] = {
                "metrics": {sp: {k: round(m[sp][k], 4) for k in m[sp]} for sp in SPLITS_REPORT},
                "readout_hash": per_seed[s][a]["readout_hash"],
                "frozen_base_unchanged": per_seed[s][a]["frozen_base_unchanged"],
            }

    arm_results = {a: G.eval_arm(a, [cm(a, s) for s in seeds], r0_seed_T4) for a in C.ARMS}

    integrity_ok = bool(data["determinism"]["byte_identical"] and data["oracle_equivariance"]["pass"]
                        and data["leakage_all_pass"] and data["frozen_base_unchanged_all"]
                        and data["frozen_base_matches_lock"] and data["source_hashes_match_lock"])
    concl = G.conclude(arm_results, added, integrity_ok)

    def arm_mean(a, split, key):
        return sum(cm(a, s)[split][key] for s in seeds) / len(seeds)

    t5 = {a: round(arm_mean(a, "T5_pred_succ", "correct_latest"), 4) for a in C.ARMS}

    analysis = {
        "schema": "bindingslots_e1_readout/analysis/v1",
        "reference_arm": C.REFERENCE_ARM,
        "mean_T4_null_inclusive": {a: round(arm_results[a]["mean_T4"], 4) for a in C.ARMS},
        "mean_T4_null_excluded_addressing": {a: round(arm_mean(a, "T4_latest", "addressing_top1"), 4) for a in C.ARMS},
        "mean_improvement_over_R0": {a: round(arm_results[a]["mean_improvement_over_R0"], 4) for a in C.ARMS},
        "worst_seed_T4": {a: round(arm_results[a]["worst_seed_T4"], 4) for a in C.ARMS},
        "present_seed_pass": {a: arm_results[a]["present_seed_pass"] for a in C.ARMS},
        "partial_seed_pass": {a: arm_results[a]["partial_seed_pass"] for a in C.ARMS},
        "present_flag": {a: arm_results[a]["present"] for a in C.ARMS},
        "partial_flag": {a: arm_results[a]["partial"] for a in C.ARMS},
        "added_params_per_arm": added,
        "component_means": {a: {
            "null_rate": round(arm_mean(a, "T4_latest", "null_rate"), 4),
            "wrong_entity": round(arm_mean(a, "T4_latest", "wrong_entity"), 4),
            "right_entity_wrong_older": round(arm_mean(a, "T4_latest", "right_entity_wrong_older"), 4),
            "correct_entity": round(arm_mean(a, "T4_latest", "correct_entity"), 4),
            "e2e": round(arm_mean(a, "T4_latest", "e2e"), 4),
        } for a in C.ARMS},
        "integrity_ok": integrity_ok,
        "determinism_ok": bool(data["determinism"]["byte_identical"] and data["oracle_equivariance"]["pass"]),
        "leakage_ok": bool(data["leakage_all_pass"]),
        "frozen_base_unchanged": bool(data["frozen_base_unchanged_all"] and data["frozen_base_matches_lock"]),
        "shortcut_baselines": data["leakage"]["shortcut_baselines"],
        "selection_rule": lock["selection_rule"],
        "conclusion": concl["conclusion"],
        "selected_arm": concl["selected_arm"],
        "structural_prior_only_signal": concl["structural_prior_only"],
        "preserved": concl["preserved"],
        "never_emit": C.NEVER_EMIT,
        "t5_diagnostic_only": t5,
        "gates": C.GATES,
        "interpretation": _interpret(concl, arm_results),
    }
    _w("readout_analysis.json", analysis)
    _w("final_report.json", {"schema": "bindingslots_e1_readout/report_table/v1", "table": table,
                             "conclusion": concl["conclusion"], "selected_arm": concl["selected_arm"],
                             "structural_prior_only_signal": concl["structural_prior_only"],
                             "preserved": concl["preserved"]})

    print("CONCLUSION:", concl["conclusion"], "| selected:", concl["selected_arm"],
          "| structural_prior_only:", concl["structural_prior_only"])
    print("mean T4 (null-incl):", {a: round(arm_results[a]["mean_T4"], 3) for a in C.ARMS})
    print("mean improvement over R0:", {a: round(arm_results[a]["mean_improvement_over_R0"], 3) for a in C.ARMS})
    print("present flags:", {a: arm_results[a]["present"] for a in C.ARMS},
          "| partial flags:", {a: arm_results[a]["partial"] for a in C.ARMS})
    print("preserved:", concl["preserved"])


def _interpret(concl, arm_results):
    c = concl["conclusion"]
    if c == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT":
        return ("The frozen temporal E1 token representations contain useful latest-state information that a "
                "learned readout can recover more effectively than mean pooling.")
    if c == "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL":
        if concl["structural_prior_only"]:
            return ("STRUCTURAL_PRIOR_ONLY_SIGNAL: frozen representations can be exploited when schema-level "
                    "token-role information is supplied (R3), but a fully learned readout did not; this does "
                    "NOT establish a learned frozen-representation signal.")
        return ("The tested learned readout recovered some latest-state signal, but not enough to establish a "
                "strong frozen-representation result.")
    if c == "FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND":
        return ("The tested frozen readouts did not recover sufficient latest-state information from the "
                "frozen temporal E1 representations.")
    return c


def _w(name, obj):
    p = RES / name
    tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(obj, indent=2, sort_keys=True)); tmp.replace(p)


if __name__ == "__main__":
    main()
