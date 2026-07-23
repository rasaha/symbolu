"""Shadow-pilot harness. Deterministic end to end.

Flow: resolve adapters -> dry-run cost + guard -> DEV counterfactual -> build
telemetry regimes -> SHADOW counterfactual -> baselines A-E -> policy F1/F2/G per
regime -> score all arms -> F1-vs-F2 and F2-vs-G ablations -> commercial vs
strongest-eligible -> routing stability -> decision records. Writes results/.

In this environment no real model is reachable, so it runs in SELF_TEST (stub)
mode: the pipeline is exercised and validated, but the numbers are NOT real-model
evidence. Supplying provider keys switches resolve_adapters to REAL mode.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from model_selection_pilot import arms as arms
from model_selection_pilot import costguard as cg
from model_selection_pilot import execute as execute
from model_selection_pilot import metrics as metrics
from model_selection_pilot import policy as pol
from model_selection_pilot import telemetry as tele
from model_selection_pilot.advisory import PREFLIGHT_TOKENS_IN, PREFLIGHT_TOKENS_OUT
from model_selection_pilot.common import REGIMES, RESULTS_DIR, load_json, save_json
from model_selection_pilot.provider import resolve_adapters

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAX_SPEND_USD = float(os.environ.get("PILOT_MAX_SPEND_USD", "5.00"))


def _preflight_cost_map(registry, g_records) -> Dict[str, float]:
    out = {}
    for tid, rec in g_records.items():
        cands = [g["model"] for g in rec.get("gate", [])]
        c = 0.0
        for mid in cands:
            c += cg.model_call_cost(registry["models"][mid], PREFLIGHT_TOKENS_IN, PREFLIGHT_TOKENS_OUT)
        out[tid] = c
    return out


def _preflight_latency_map(g_records) -> Dict[str, float]:
    return {tid: rec.get("preflight_latency_ms", 0.0) for tid, rec in g_records.items()}


def run() -> Dict[str, Any]:
    registry = load_json(os.path.join(DATA, "registry.json"))
    dev = load_json(os.path.join(DATA, "corpus_dev.json"))["tasks"]
    shadow = load_json(os.path.join(DATA, "corpus_shadow.json"))["tasks"]

    adapters, adapter_status = resolve_adapters(registry)
    mode = adapter_status["mode"]

    # --- cost guard: dry-run + worst-case + hard cap ---
    dry_dev = cg.dry_run(registry, dev, execute.technically_eligible)
    dry_shadow = cg.dry_run(registry, shadow, execute.technically_eligible)
    worst = dry_dev["worst_case_usd"] + dry_shadow["worst_case_usd"]
    guard = cg.CostGuard(MAX_SPEND_USD)
    cost_report = {"mode": mode, "max_spend_usd": MAX_SPEND_USD,
                   "dev": dry_dev, "shadow": dry_shadow, "combined_worst_case_usd": round(worst, 4),
                   "note": ("SELF_TEST: real API spend is $0; figures are MODELED from registry price."
                            if mode == "SELF_TEST" else "REAL: guard will abort before exceeding cap.")}
    if mode == "REAL" and worst > MAX_SPEND_USD:
        cost_report["preflight_decision"] = "worst-case exceeds cap; proceeding with per-call guard"

    # --- counterfactual executions ---
    dev_cf = execute.run_counterfactual(registry, adapters, dev, guard)
    shadow_cf = execute.run_counterfactual(registry, adapters, shadow, guard)
    dev_results, shadow_results = dev_cf["normalized"], shadow_cf["normalized"]

    # --- telemetry snapshots from DEV (regime-gated) ---
    snaps = tele.build_snapshots(dev_results, dev, registry["version"])
    benchmark = snaps["full"]

    # --- baselines A-E (regime-invariant) on SHADOW ---
    baseline_sel = {a: {t["task_id"]: fn(registry, t, benchmark) for t in shadow}
                    for a, fn in arms.BASELINES.items()}

    # --- advisory (arm G): collected from adapters as a preflight, task-shape only ---
    advisory_map = {t["task_id"]: {mid: adapters[mid].self_assess(pol.routing_view(t))
                                   for mid in registry["models"]} for t in shadow}

    # --- policy arms F1/F2/G per regime on SHADOW ---
    policy_records: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for regime in REGIMES:
        snap = snaps[regime]
        for mode_name in ("F1", "F2", "G"):
            key = f"{mode_name}:{regime}"
            amap = advisory_map if mode_name == "G" else None
            policy_records[key] = {
                t["task_id"]: pol.route(t, registry, snap, regime, mode_name,
                                        advisory_map.get(t["task_id"]) if mode_name == "G" else None)
                for t in shadow}

    # --- scoring ---
    scores: Dict[str, Any] = {"baselines": {}, "policy": {}}
    for a in arms.BASELINES:
        scores["baselines"][a] = metrics.score_arm(a, baseline_sel[a], shadow, shadow_results)
    for key, recs in policy_records.items():
        mode_name, regime = key.split(":")
        pf_cost = _preflight_cost_map(registry, recs) if mode_name == "G" else {}
        pf_lat = _preflight_latency_map(recs) if mode_name == "G" else {}
        scores["policy"][key] = metrics.score_arm(key, recs, shadow, shadow_results, pf_cost, pf_lat)

    # --- mandated ablations ---
    ablation_f1_f2 = {}
    ablation_f2_g = {}
    for regime in REGIMES:
        f1, f2 = scores["policy"][f"F1:{regime}"], scores["policy"][f"F2:{regime}"]
        g = scores["policy"][f"G:{regime}"]
        ablation_f1_f2[regime] = {m: _delta(f2, f1, m) for m in
                                  ("mean_selection_regret", "quality_threshold_success_rate",
                                   "constraint_violation_rate", "abstention_rate")}
        ablation_f2_g[regime] = {m: _delta(g, f2, m) for m in
                                 ("mean_selection_regret", "quality_threshold_success_rate",
                                  "mean_cost_per_successful_task", "abstention_rate")}

    # --- commercial vs strongest-eligible (B), for F2 and G at mature ---
    commercial = {
        "F2_mature_vs_B": metrics.commercial_vs_baseline(
            policy_records["F2:mature"], baseline_sel["B"], shadow, shadow_results),
        "G_mature_vs_B": metrics.commercial_vs_baseline(
            policy_records["G:mature"], baseline_sel["B"], shadow, shadow_results,
            _preflight_cost_map(registry, policy_records["G:mature"])),
    }

    # --- routing stability (F2 mature under +/-1% telemetry perturbation) ---
    pert = {mid: {tc: (dict(v, quality_mean=(None if v["quality_mean"] is None
                        else min(1.0, v["quality_mean"] * 1.01))) if isinstance(v, dict) else v)
                  for tc, v in cls.items()} for mid, cls in snaps["mature"].items() if mid != "_version"}
    pert["_version"] = snaps["mature"]["_version"] + ":pert"
    unchanged = sum(1 for t in shadow
                    if pol.route(t, registry, snaps["mature"], "mature", "F2")["selected"]
                    == pol.route(t, registry, pert, "mature", "F2")["selected"])
    stability = round(unchanged / len(shadow), 4)

    # --- persist ---
    save_json(os.path.join(RESULTS_DIR, "raw", "shadow_raw.json"), shadow_cf["raw"])
    save_json(os.path.join(RESULTS_DIR, "normalized", "dev_normalized.json"), dev_results)
    save_json(os.path.join(RESULTS_DIR, "normalized", "shadow_normalized.json"), shadow_results)
    save_json(os.path.join(RESULTS_DIR, "decision_records_F2_G_mature.json"),
              {"F2": policy_records["F2:mature"], "G": policy_records["G:mature"]})
    sample_ids = [t["task_id"] for t in shadow[:4]] + \
                 [t["task_id"] for t in shadow if t.get("hard_constraints", {}).get("require_on_prem")][:1]
    save_json(os.path.join(RESULTS_DIR, "decision_record_samples.json"),
              {tid: {"F2": policy_records["F2:mature"].get(tid), "G": policy_records["G:mature"].get(tid)}
               for tid in sample_ids})

    results = {
        "mode": mode, "adapter_status": adapter_status, "cost_report": cost_report,
        "registry_version": registry["version"], "n_dev": len(dev), "n_shadow": len(shadow),
        "scores": scores, "ablation_F1_vs_F2": ablation_f1_f2, "ablation_F2_vs_G": ablation_f2_g,
        "commercial": commercial, "routing_stability_F2_mature": stability,
        "self_test_disclaimer": (None if mode == "REAL" else
            "SELF_TEST MODE: all numeric results derive from a deterministic offline STUB and are "
            "NOT real-model evidence. They validate that the harness runs correctly. The empirical "
            "question remains OPEN pending execution against real models (see PILOT_STATUS.md)."),
    }
    save_json(os.path.join(RESULTS_DIR, "aggregate.json"), results)
    return results


def _delta(a, b, m):
    if a.get(m) is None or b.get(m) is None:
        return None
    return round(a[m] - b[m], 4)


def print_summary(res: Dict[str, Any]) -> None:
    print(f"\nMODE: {res['mode']}")
    if res["self_test_disclaimer"]:
        print("!! " + res["self_test_disclaimer"])
    cr = res["cost_report"]
    print(f"\nCost guard: cap ${cr['max_spend_usd']}, combined worst-case ${cr['combined_worst_case_usd']} "
          f"({cr['note']})")
    print("\n== baselines (shadow) ==")
    hdr = f"{'arm':>3} {'regret':>8} {'viol':>6} {'qok':>6} {'$/ok':>10} {'p95ms':>8} {'exp.avoid':>9}"
    print(hdr)
    for a in ("A", "B", "C", "D", "E"):
        m = res["scores"]["baselines"][a]
        print(f"{a:>3} {m['mean_selection_regret']:>8} {m['constraint_violation_rate']:>6} "
              f"{m['quality_threshold_success_rate']:>6} {str(m['mean_cost_per_successful_task']):>10} "
              f"{str(m['p95_latency_ms']):>8} {m['expensive_model_avoided_rate']:>9}")
    print("\n== policy arms by regime ==")
    print(hdr + f" {'explOK':>7}")
    for regime in REGIMES:
        for mode_name in ("F1", "F2", "G"):
            m = res["scores"]["policy"][f"{mode_name}:{regime}"]
            print(f"{mode_name+'/'+regime[:4]:>9} {m['mean_selection_regret']:>8} "
                  f"{m['constraint_violation_rate']:>6} {m['quality_threshold_success_rate']:>6} "
                  f"{str(m['mean_cost_per_successful_task']):>10} {str(m['p95_latency_ms']):>8} "
                  f"{m['expensive_model_avoided_rate']:>9} {str(m['explanation_completeness_rate']):>7}")
    print("\n== ablation F2 - F1 (quality-gate correction) ==")
    for regime in REGIMES:
        d = res["ablation_F1_vs_F2"][regime]
        print(f" {regime:8} dRegret={d['mean_selection_regret']} dQok={d['quality_threshold_success_rate']} "
              f"dViol={d['constraint_violation_rate']} dAbstain={d['abstention_rate']}")
    print("\n== ablation G - F2 (cold-start self-assessment) ==")
    for regime in REGIMES:
        d = res["ablation_F2_vs_G"][regime]
        print(f" {regime:8} dRegret={d['mean_selection_regret']} dQok={d['quality_threshold_success_rate']} "
              f"d$/ok={d['mean_cost_per_successful_task']}")
    print("\n== commercial (F2 mature vs strongest-eligible B) ==")
    print("  ", res["commercial"]["F2_mature_vs_B"])
    print(f"\nrouting stability (F2 mature, +/-1% perturbation): {res['routing_stability_F2_mature']}")


if __name__ == "__main__":
    print_summary(run())
