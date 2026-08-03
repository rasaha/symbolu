#!/usr/bin/env python3
"""Build the curated confirmatory result artifacts from the raw per-(arm,seed) result JSONs.

Produces (under results/):
  aggregate_result.json, classifier_output.json, causal_gate_output.json, quality_gate_output.json,
  distance_gate_output.json, retention_diagnostics.json, baseline_comparison.json,
  integrity_report.json, and seeds/seed_<n>_<arm>.json curated per-seed files.

Reads the raw results/seeds/<arm>_results.json produced by run_confirmatory.py. Pure stdlib
(imports classify_confirmatory which only needs stdlib). Deterministic.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import statistics as st
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import classify_confirmatory as C  # noqa: E402
import retention as RET  # noqa: E402

RESULTS = HERE / "results"
SEED_DIR = RESULTS / "seeds"
SEEDS = [13, 14, 15, 16, 17]
FROZEN = json.loads((HERE / "frozen_cr1_config.json").read_text())


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load(arm):
    p = SEED_DIR / f"{arm}_results.json"
    return {r["seed"]: r for r in json.loads(p.read_text())["records"]}


def integrity_report():
    checks = []
    ok = True
    for rel, want in FROZEN["frozen_code_hashes_sha256"].items():
        got = sha256(REPO / rel)
        good = got == want
        ok = ok and good
        checks.append({"file": rel, "expected": want[:16], "got": got[:16], "ok": good})
    manifest = json.loads((RESULTS / "manifest.json").read_text()) if (RESULTS / "manifest.json").exists() else {}
    abc_before = manifest.get("abc_json_sha256_before")
    abc_after = sha256(REPO / "experiments/phase_lc/results/abc.json")
    abc_ok = (abc_before == abc_after == "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482")
    ok = ok and abc_ok
    return {
        "schema": "bindingslots_confirmatory/integrity_report/v1",
        "frozen_code_hashes_ok": all(c["ok"] for c in checks),
        "frozen_code_checks": checks,
        "abc_json_sha256_before": abc_before,
        "abc_json_sha256_after": abc_after,
        "abc_json_unchanged": abc_ok,
        "integrity_ok": ok,
    }, ok


def main():
    cr1, ap, b0 = load("CR1"), load("A+"), load("B0")
    integ, integ_ok = integrity_report()

    agg = C.classify(cr1, ap, b0, integrity_ok=integ_ok, protocol_deviations=[])
    (RESULTS / "aggregate_result.json").write_text(json.dumps(agg, indent=2) + "\n")
    (RESULTS / "classifier_output.json").write_text(json.dumps({
        "primary_verdict": agg["primary_verdict"],
        "slot_formation_status": agg["slot_formation_status"],
        "kda_readiness": agg["kda_readiness"],
        "gates": agg["gates"], "all_gates_pass": agg["all_gates_pass"],
        "cr1_formation_count": agg["cr1_formation_count"],
        "b0_formation_count": agg["b0_formation_count"],
        "forming": agg["forming"],
    }, indent=2) + "\n")

    # causal gate output (per forming seed, both ablations, all recorded ablations)
    causal = {"schema": "bindingslots_confirmatory/causal_gate_output/v1", "by_forming_seed": {}}
    for s in SEEDS:
        if not agg["forming"][str(s)]:
            continue
        ab = cr1[s].get("ablation", {})
        causal["by_forming_seed"][str(s)] = {
            "baseline": ab.get("baseline", cr1[s]["needle_by_dist"]["96"]),
            "slots_off": ab.get("slots_off"),
            "randomized_address": ab.get("randomized_address"),
            "shuffle_values": ab.get("shuffle_values"),
            "write_gate_zero": ab.get("write_gate_zero"),
            "slot_keys_randomized": ab.get("slot_keys_randomized"),
            "aplus_d96": ap[s]["needle_by_dist"]["96"],
            "verdict": agg["causal_by_forming_seed"].get(str(s)),
        }
    causal["all_forming_seeds_clean"] = agg["gates"]["C8_slots_off"] and agg["gates"]["C9_randomized_address"]
    (RESULTS / "causal_gate_output.json").write_text(json.dumps(causal, indent=2) + "\n")

    # quality gate
    q = {"schema": "bindingslots_confirmatory/quality_gate_output/v1",
         "per_seed": {str(s): {"CR1_ppl256": cr1[s]["ppl"]["256"], "B0_ppl256": b0[s]["ppl"]["256"],
                               "Aplus_ppl256": ap[s]["ppl"]["256"]} for s in SEEDS},
         "mean_CR1_ppl256": round(st.mean([cr1[s]["ppl"]["256"] for s in SEEDS]), 2),
         "mean_Aplus_ppl256": round(st.mean([ap[s]["ppl"]["256"] for s in SEEDS]), 2),
         "median_CR1_ppl256": round(st.median([cr1[s]["ppl"]["256"] for s in SEEDS]), 2),
         "threshold": "mean(CR1) <= 1.20 * mean(A+); <= 2 of 5 exceed A+ by >25%",
         "pass": agg["quality"]["pass"]}
    (RESULTS / "quality_gate_output.json").write_text(json.dumps(q, indent=2) + "\n")

    # distance gate — per seed and aggregate, incl slots-off / random-address at each distance where available
    dist = {"schema": "bindingslots_confirmatory/distance_gate_output/v1", "per_seed": {}}
    for s in SEEDS:
        dist["per_seed"][str(s)] = {
            "CR1": cr1[s]["needle_by_dist"], "A+": ap[s]["needle_by_dist"], "B0": b0[s]["needle_by_dist"],
        }
    for d in ("16", "96", "220"):
        dist[f"aggregate_d{d}_CR1_mean"] = round(st.mean([cr1[s]["needle_by_dist"][d] for s in SEEDS]), 4)
        dist[f"aggregate_d{d}_Aplus_mean"] = round(st.mean([ap[s]["needle_by_dist"][d] for s in SEEDS]), 4)
    dist["gate"] = agg["distance"]
    (RESULTS / "distance_gate_output.json").write_text(json.dumps(dist, indent=2) + "\n")

    # retention diagnostics
    ret = {"schema": "bindingslots_confirmatory/retention_diagnostics/v1",
           "by_seed": agg["retention_by_seed"],
           "formed_and_retained": sum(1 for v in agg["retention_by_seed"].values() if v == "FORMED_AND_RETAINED"),
           "formed_then_collapsed": sum(1 for v in agg["retention_by_seed"].values() if v == "FORMED_THEN_COLLAPSED"),
           "trajectories_d96": {str(s): RET.trajectory_d96(cr1[s]) for s in SEEDS}}
    (RESULTS / "retention_diagnostics.json").write_text(json.dumps(ret, indent=2) + "\n")

    # baseline comparison (CR1 vs B0 and vs A+)
    base = {"schema": "bindingslots_confirmatory/baseline_comparison/v1",
            "cr1_formation_count": agg["cr1_formation_count"],
            "b0_formation_count": agg["b0_formation_count"],
            "aplus_formation_count": agg["aplus_formation_count"],
            "cr1_gt_b0_formation": agg["gates"]["C2_form_gt_B0"],
            "paired_wins_vs_Aplus": agg["win_count"],
            "mean_margin_vs_Aplus": agg["mean_margin"],
            "median_margin_vs_Aplus": agg["median_margin"],
            "per_seed_needle_d96": agg["needle_d96"]}
    (RESULTS / "baseline_comparison.json").write_text(json.dumps(base, indent=2) + "\n")

    (RESULTS / "integrity_report.json").write_text(json.dumps(integ, indent=2) + "\n")

    # curated per-seed files (seed_<n>_<arm>.json)
    for s in SEEDS:
        for arm, byseed in (("a+", ap), ("b0", b0), ("cr1", cr1)):
            (SEED_DIR / f"seed_{s}_{arm}.json").write_text(json.dumps(byseed[s], indent=2) + "\n")

    print(json.dumps({"primary_verdict": agg["primary_verdict"],
                      "cr1_formation_count": agg["cr1_formation_count"],
                      "b0_formation_count": agg["b0_formation_count"],
                      "kda_readiness": agg["kda_readiness"],
                      "integrity_ok": integ_ok}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
