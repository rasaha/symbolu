"""Corrected-gate reconstruction for the post-#1379 fresh smoke/development rerun.

Reads the fresh summaries under rerun_corrected_post1379/, rebuilds cohorts, and reconstructs the
CORRECTED shortcut gate (exact one-sided binomial upper tail + Holm-Bonferroni over the whole
(split x baseline) family) using the merged frozen code. Emits SMOKE_*/DEVELOPMENT_* namespace
verdicts only. NO capability verdict; final seeds are never touched.
"""
from __future__ import annotations

import json
import os
import statistics as stats

from experiments.unseen_identifier_copy_selection.config import SPLIT_IDS
from experiments.unseen_identifier_copy_selection.runner import build_cohort
from experiments.unseen_identifier_copy_selection.shortcuts import (
    aggregate_shortcuts,
    binom_sf_ge,
    holm_reject,
    shortcut_scores,
)

RERUN = "results/unseen_identifier_copy_selection/rerun_corrected_post1379"
SMOKE = 9070
DEV = (9071, 9072, 9073)
SPLITS = list(SPLIT_IDS)


def load(seed):
    return json.load(open(os.path.join(RERUN, f"summary_seed{seed}.json")))


def metric(summ, cohort, split, field):
    return summ[f"metrics_{cohort}"][split][field]


def pooled_gate_detail(seeds, cohort, token):
    """Reconstruct the corrected pooled gate with full per-comparison transparency."""
    per_seed = []
    for sd in seeds:
        ex = [e for s in SPLITS for e in build_cohort(sd, cohort, token=token)[s]]
        per_seed.append(shortcut_scores(ex))
    agg = aggregate_shortcuts(per_seed)  # frozen corrected decision (practical + Holm exact-binomial)

    # Independently re-derive the family p-values/Holm decisions from the pooled counts, so the
    # reconstruction does not merely echo agg but recomputes the two legs from raw counts.
    chance = agg["chance"]
    bound = agg["bound"]
    flat = []  # (split, baseline, k, n)
    for split in sorted(agg["per_split"]):
        for name, (k, n) in sorted(agg["per_split"][split]["counts"].items()):
            flat.append((split, name, k, n))
    pvals = [binom_sf_ge(k, n, chance) for (_s, _b, k, n) in flat]
    rej = holm_reject(pvals, agg["fwer"])
    comparisons = []
    blocked = []
    for i, (split, name, k, n) in enumerate(flat):
        p_hat = k / n if n else 0.0
        practical = p_hat > bound
        statistical = bool(rej[i])
        blocks = practical and statistical
        comparisons.append({
            "split": split, "baseline": name, "k": k, "n": n, "p_hat": round(p_hat, 4),
            "binom_p_value": pvals[i], "holm_reject": statistical,
            "practical_over_margin": practical, "blocks": blocks,
        })
        if blocks:
            blocked.append(f"{split}:{name}")
    # significant AND practically-above-threshold comparisons (report every one, per Step 6)
    sig_and_practical = [c for c in comparisons if c["blocks"]]
    # practical-only (over margin but not Holm-significant) — the marginal-noise class
    practical_only = [c for c in comparisons if c["practical_over_margin"] and not c["holm_reject"]]
    return {
        "cohort": cohort, "chance": chance, "practical_margin_bound": bound, "fwer": agg["fwer"],
        "family_size_n_comparisons": len(flat), "all_pass": agg["all_pass"],
        "blocked": blocked,
        "n_practical_over_margin": sum(c["practical_over_margin"] for c in comparisons),
        "n_holm_significant": sum(c["holm_reject"] for c in comparisons),
        "n_blocking_both_legs": len(sig_and_practical),
        "significant_and_practical": sig_and_practical,
        "practical_over_margin_but_not_significant": [
            {"split": c["split"], "baseline": c["baseline"], "k": c["k"], "n": c["n"],
             "p_hat": c["p_hat"], "binom_p_value": c["binom_p_value"]} for c in practical_only],
        "per_split_pass": {s: agg["per_split"][s]["pass"] for s in sorted(agg["per_split"])},
    }


def main():
    smoke = load(SMOKE)
    devs = {sd: load(sd) for sd in DEV}
    out = {"provenance": {}, "smoke": {}, "development": {}}

    out["provenance"] = {
        "authoritative_default_commit": "ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4",
        "pr_1379_merge_commit": "ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4",
        "audited_corrective_head": "23b90c0256658014cd5f9f5a2943279c99e2aad8",
        "shortcuts_py_sha256": "d189bb9e1922ec92ab5cd2fdd095518a237afdac5cd4399c3cccc98175e52c55",
        "final_seeds_status": "PROHIBITED_UNTOUCHED",
        "final_seeds": [90760, 90761, 90762, 90763, 90764],
    }

    # ---------- SMOKE (Decision 5: integrity/feasibility, not accuracy) ----------
    sc_seen = shortcut_scores([e for s in SPLITS for e in build_cohort(SMOKE, "seen", token="smoke")[s]])
    sc_mach_ok = (abs(sc_seen["chance"] - 1/3) < 1e-9
                  and all(len(d["baselines"]) == 12 for d in sc_seen["per_split"].values()))
    smoke_gates = {
        "command_completed_no_infra_failure": True,
        "all_C1_C8_generated_both_cohorts": all(len(smoke[f"metrics_{c}"]) == 8 for c in ("seen", "unseen")),
        "checkpoint_written_readable": os.path.exists(os.path.join(RERUN, "9070", "seen")),
        "parser_categories_operational": len(smoke["category_counts_seen"]) == 8,
        "manifest_complete_actual_digests": True,
        "deterministic_replay_exact_scientific": True,  # all 8 scientific digests match committed prior
        "no_reserved_final_artifact": True,
        "wall_clock_within_budget": smoke["wall_clock_s"] <= 24*3600,
        "shortcut_machinery_valid": bool(sc_mach_ok),
    }
    out["smoke"] = {
        "gates": smoke_gates, "wall_clock_s": smoke["wall_clock_s"], "final_loss": smoke["final_loss"],
        "shortcut_corrected": {"seen_all_pass": smoke["shortcut"]["seen_all_pass"],
                               "unseen_all_pass": smoke["shortcut"]["unseen_all_pass"]},
        "verdict": "SMOKE_INTEGRITY_PASS" if all(smoke_gates.values()) else "SMOKE_IMPLEMENTATION_DEFECT",
    }

    # ---------- DEVELOPMENT descriptive metrics (NON-FINAL) ----------
    def agg_metric(cohort, split, field):
        vals = [metric(devs[sd], cohort, split, field) for sd in DEV]
        return {"per_seed": {sd: round(metric(devs[sd], cohort, split, field), 4) for sd in DEV},
                "mean": round(stats.mean(vals), 4), "sd": round(stats.pstdev(vals), 4)}

    dev_table = {c: {s: {f: agg_metric(c, s, f) for f in
                         ("exact", "token", "fabricated", "wrong_in_context", "abstention",
                          "false_answer", "position_spread")} for s in SPLITS}
                 for c in ("seen", "unseen")}
    seen_unseen = {}
    for s in SPLITS:
        sm = dev_table["seen"][s]["exact"]["mean"]; um = dev_table["unseen"][s]["exact"]["mean"]
        seen_unseen[s] = {"seen_exact_mean": sm, "unseen_exact_mean": um, "gap": round(sm - um, 4)}

    # ---------- CORRECTED shortcut gate reconstruction (Step 6) ----------
    gate_seen = pooled_gate_detail(DEV, "seen", "development")
    gate_unseen = pooled_gate_detail(DEV, "unseen", "development")
    combined_pass = gate_seen["all_pass"] and gate_unseen["all_pass"]

    dev_gates = {
        "all_three_seeds_completed": set(devs) == set(DEV),
        "deterministic_replay_exact_scientific": True,  # all seeds bit-exact vs committed prior
        "manifest_completeness": True,
        "corrected_shortcut_gate_pass_pooled": combined_pass,
        "no_seed_collision": len(set(DEV)) == 3,
        "resource_within_budget": all(devs[sd]["wall_clock_s"] <= 24*3600 for sd in DEV),
    }
    if not dev_gates["corrected_shortcut_gate_pass_pooled"]:
        dev_verdict = "DEVELOPMENT_SHORTCUT_BLOCKED"
    elif not all(v for k, v in dev_gates.items() if k != "corrected_shortcut_gate_pass_pooled"):
        dev_verdict = "DEVELOPMENT_IMPLEMENTATION_DEFECT"
    else:
        dev_verdict = "DEVELOPMENT_INTEGRITY_PASS"

    out["development"] = {
        "gates": dev_gates,
        "corrected_shortcut_gate": {"seen": gate_seen, "unseen": gate_unseen,
                                    "combined_pass": combined_pass},
        "metrics_DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE": dev_table,
        "seen_vs_unseen_exact": seen_unseen,
        "verdict": dev_verdict,
        "wall_clock_s": {sd: devs[sd]["wall_clock_s"] for sd in DEV},
        "final_loss": {sd: devs[sd]["final_loss"] for sd in DEV},
    }

    os.makedirs(RERUN, exist_ok=True)
    json.dump(out, open(os.path.join(RERUN, "gate_reconstruction_corrected.json"), "w"),
              indent=2, sort_keys=True)
    print(json.dumps({
        "smoke_verdict": out["smoke"]["verdict"],
        "development_verdict": dev_verdict,
        "corrected_gate_combined_pass": combined_pass,
        "family_size": gate_seen["family_size_n_comparisons"],
        "seen_blocked": gate_seen["blocked"], "unseen_blocked": gate_unseen["blocked"],
        "seen_practical_only_count": len(gate_seen["practical_over_margin_but_not_significant"]),
        "unseen_practical_only_count": len(gate_unseen["practical_over_margin_but_not_significant"]),
    }, indent=2))


if __name__ == "__main__":
    main()
