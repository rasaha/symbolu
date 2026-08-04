#!/usr/bin/env python3
"""Curate the functional-routing Stage-1 result artifacts from raw per-(arm,seed) JSON. Deterministic,
pure stdlib (imports fr_classifier). Run after fr_runner completes."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import fr_classifier as FC  # noqa: E402

RESULTS = HERE / "results"
SEED_DIR = RESULTS / "seeds"
SEEDS = FC.SEEDS
FROZEN = json.loads((HERE / "frozen_reference_config.json").read_text())


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load(arm):
    return {r["seed"]: r for r in json.loads((SEED_DIR / f"{arm}_results.json").read_text())["records"]}


def integrity():
    checks = {rel: (sha256(REPO / rel) == want) for rel, want in FROZEN["frozen_code_hashes_sha256"].items()}
    abc = sha256(REPO / "experiments/phase_lc/results/abc.json")
    man = json.loads((RESULTS / "stage1_manifest.json").read_text()) if (RESULTS / "stage1_manifest.json").exists() else {}
    ok = all(checks.values()) and abc == "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482"
    return {"schema": "bindingslots_functional_routing/integrity_report/v1",
            "frozen_code_hashes_ok": all(checks.values()), "per_file": checks,
            "abc_json_sha256_before": man.get("abc_json_sha256_before"),
            "abc_json_sha256_after": abc, "abc_unchanged": ok, "integrity_ok": ok}, ok


def main():
    arms = {a: load(a) for a in ("A+", "R0", "O1", "O2", "H3")}
    integ, integ_ok = integrity()
    agg = FC.classify(str(SEED_DIR), integrity_ok=integ_ok)
    (RESULTS / "stage1_aggregate.json").write_text(json.dumps(agg, indent=2) + "\n")
    (RESULTS / "stage1_classifier_output.json").write_text(json.dumps(
        {k: agg.get(k) for k in ("primary_verdict", "selected_candidate", "kda_readiness", "summaries")}, indent=2) + "\n")
    (RESULTS / "stage1_selection_decision.json").write_text(json.dumps(
        {"primary_verdict": agg["primary_verdict"], "selected_candidate": agg.get("selected_candidate"),
         "tie_break_order": FC.SINGLE_TIE_BREAK,
         "clearing_arms": [a for a in ("O1", "O2", "H3", "R0") if agg.get("summaries", {}).get(a, {}).get("full_single_gate")]},
        indent=2) + "\n")

    # routing-metric analysis (per arm/seed at 1200)
    def routing_row(rec):
        r = FC.routing_at(rec, 1200)
        return {"needle_d96": FC.FROZEN.d(rec, 96), "correct_slot_prob": r.get("read_prob_on_highest_write_slot"),
                "rank": r.get("rank_of_highest_write_slot_under_read"), "margin": r.get("address_logit_margin"),
                "aggregate_overlap": r.get("write_read_overlap")}
    rma = {"schema": "bindingslots_functional_routing/routing_metric_analysis/v1",
           "by_arm": {a: {str(s): routing_row(arms[a][s]) for s in SEEDS} for a in ("R0", "O1", "O2", "H3")}}
    (RESULTS / "routing_metric_analysis.json").write_text(json.dumps(rma, indent=2) + "\n")

    # causal-purity analysis (final formers per arm)
    cpa = {"schema": "bindingslots_functional_routing/causal_purity_analysis/v1", "by_arm": {}}
    for a in ("R0", "O1", "O2", "H3"):
        formers = [s for s in SEEDS if FC.FROZEN.forming(arms[a][s], arms["A+"][s])]
        cpa["by_arm"][a] = {str(s): {"baseline": arms[a][s].get("ablation", {}).get("baseline"),
                                     "slots_off": arms[a][s].get("ablation", {}).get("slots_off"),
                                     "randomized_address": arms[a][s].get("ablation", {}).get("randomized_address"),
                                     "slots_off_ok": FC.slots_off_ok(arms[a][s], arms["A+"][s]),
                                     "rand_addr_ok": FC.rand_addr_ok(arms[a][s], arms["A+"][s])} for s in formers}
    (RESULTS / "causal_purity_analysis.json").write_text(json.dumps(cpa, indent=2) + "\n")

    # retention analysis (trajectories + states)
    rta = {"schema": "bindingslots_functional_routing/retention_analysis/v1", "by_arm": {}}
    for a in ("R0", "O1", "O2", "H3"):
        rta["by_arm"][a] = {str(s): {"state": FC.per_seed_state(arms[a][s], arms["A+"][s]),
                                     "needle_trajectory": FC.needle_traj(arms[a][s])} for s in SEEDS}
    (RESULTS / "retention_analysis.json").write_text(json.dumps(rta, indent=2) + "\n")

    # quality + distance
    import statistics as st
    q = {"schema": "bindingslots_functional_routing/quality_gate/v1",
         "by_arm": {a: {"mean_ppl256": round(st.mean([arms[a][s]["ppl"]["256"] for s in SEEDS]), 2),
                        "per_seed": {str(s): arms[a][s]["ppl"]["256"] for s in SEEDS}} for a in ("A+", "R0", "O1", "O2", "H3")}}
    (RESULTS / "quality_gate.json").write_text(json.dumps(q, indent=2) + "\n")
    dist = {"schema": "bindingslots_functional_routing/distance_gate/v1",
            "by_arm": {a: {str(s): arms[a][s]["needle_by_dist"] for s in SEEDS} for a in ("A+", "R0", "O1", "O2", "H3")}}
    (RESULTS / "distance_gate.json").write_text(json.dumps(dist, indent=2) + "\n")

    (RESULTS / "integrity_report.json").write_text(json.dumps(integ, indent=2) + "\n")

    # curated per-seed files + hashes
    hashes = {}
    for s in SEEDS:
        for a in ("a+", "r0", "o1", "o2", "h3"):
            key = {"a+": "A+", "r0": "R0", "o1": "O1", "o2": "O2", "h3": "H3"}[a]
            fp = SEED_DIR / f"seed_{s}_{a}.json"
            fp.write_text(json.dumps(arms[key][s], indent=2) + "\n")
            hashes[fp.name] = sha256(fp)
    (RESULTS / "artifact_hashes.json").write_text(json.dumps(
        {"schema": "bindingslots_functional_routing/artifact_hashes/v1", "seed_files": hashes}, indent=2) + "\n")

    print(json.dumps({"primary_verdict": agg["primary_verdict"], "selected": agg.get("selected_candidate"),
                      "kda_readiness": agg.get("kda_readiness"), "integrity_ok": integ_ok}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
