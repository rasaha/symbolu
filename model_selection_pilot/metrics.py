"""Scoring of routing arms against the counterfactual outcome store.

All numbers are computed from ACTUAL executed outcomes (the counterfactual),
never from registry values alone. In self-test mode the "actual" outcomes are the
stub's synthetic outputs -- clearly not real-model evidence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from model_selection_pilot.common import percentile

PRIORITY_WEIGHTS = {
    "quality_first": (1.0, 0.15, 0.10), "balanced": (1.0, 0.50, 0.40),
    "cost_first": (0.7, 1.00, 0.30), "latency_first": (0.8, 0.30, 1.00),
}
VIOLATION_PENALTY = 1.5


def _eligible_actuals(task, results):
    return {mid: r for mid, r in results.get(task["task_id"], {}).items()}


def actual_utility(task, mid, results) -> Optional[float]:
    elig = _eligible_actuals(task, results)
    if mid not in elig:
        return None  # ineligible / not run
    wq, wc, wl = PRIORITY_WEIGHTS[task.get("business_priority", "balanced")]
    costs = [r["cost_usd"] for r in elig.values()] or [1.0]
    lats = [r["latency_ms"] for r in elig.values()] or [1.0]
    cref = max(costs) or 1e-9
    lref = max(lats) or 1e-9
    r = elig[mid]
    return wq * r["quality"] - wc * (r["cost_usd"] / cref) - wl * (r["latency_ms"] / lref)


def best_eligible(task, results):
    elig = _eligible_actuals(task, results)
    if not elig:
        return None, 0.0
    utils = {mid: actual_utility(task, mid, results) for mid in elig}
    best = max(utils, key=utils.get)
    return best, utils[best]


def score_arm(arm_name: str, selections: Dict[str, Dict[str, Any]], tasks: List[Dict[str, Any]],
              results: Dict[str, Any], preflight_cost: Dict[str, float] = None,
              preflight_latency: Dict[str, float] = None) -> Dict[str, Any]:
    preflight_cost = preflight_cost or {}
    preflight_latency = preflight_latency or {}
    n = len(tasks)
    regrets, viol, success, completions = [], 0, 0, 0
    costs_success, latencies, schema_fail, retries_sum = [], [], 0, 0
    fallback, abstain, strongest_overuse, expensive_avoided = 0, 0, 0, 0
    expl_ok, expl_checked = 0, 0

    tasks_by_id = {t["task_id"]: t for t in tasks}
    for tid, sel in selections.items():
        task = tasks_by_id[tid]
        elig = _eligible_actuals(task, results)
        best_mid, best_u = best_eligible(task, results)
        if sel.get("abstained"):
            abstain += 1
            # abstaining is correct only when no eligible model exists
            regrets.append(0.0 if not elig else best_u)
            continue
        chosen = sel["selected"]
        if chosen not in elig:  # ran an ineligible model
            viol += 1
            regrets.append(best_u + VIOLATION_PENALTY)
            continue
        u = actual_utility(task, chosen, results)
        regrets.append(max(0.0, best_u - u))
        r = elig[chosen]
        completions += 1
        retries_sum += r.get("retries", 0)
        if not r["schema_valid"]:
            schema_fail += 1
        pf_lat = preflight_latency.get(tid, 0.0)
        latencies.append(r["latency_ms"] + pf_lat)
        if r["quality"] >= task.get("min_acceptable_quality", 0.0):
            success += 1
            costs_success.append(r["cost_usd"] + preflight_cost.get(tid, 0.0))
        if sel.get("fallback_chain"):
            fallback += 1
        # expensive-model economics
        if elig:
            most_exp = max(elig, key=lambda m: elig[m]["cost_usd"])
            cheaper_ok = any(elig[m]["cost_usd"] < r["cost_usd"]
                             and elig[m]["quality"] >= task.get("min_acceptable_quality", 0.0)
                             for m in elig)
            if chosen == most_exp and cheaper_ok:
                strongest_overuse += 1
            if chosen != most_exp and r["quality"] >= task.get("min_acceptable_quality", 0.0):
                expensive_avoided += 1
        if "eliminated" in sel and "scored" in sel:  # policy arm -> check explanation
            expl_checked += 1
            if _explanation_complete(sel, set(elig) | {e["model"] for e in sel["eliminated"]}):
                expl_ok += 1

    return {
        "arm": arm_name, "n": n,
        "mean_selection_regret": round(sum(regrets) / n, 4),
        "p95_selection_regret": round(percentile(regrets, 0.95), 4),
        "constraint_violation_rate": round(viol / n, 4),
        "quality_threshold_success_rate": round(success / n, 4),
        "completion_rate": round(completions / n, 4),
        "mean_cost_per_successful_task": round(sum(costs_success) / len(costs_success), 6) if costs_success else None,
        "p50_latency_ms": round(percentile(latencies, 0.50), 1) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 0.95), 1) if latencies else None,
        "schema_failure_rate": round(schema_fail / n, 4),
        "retry_rate": round(retries_sum / n, 4),
        "fallback_rate": round(fallback / n, 4),
        "abstention_rate": round(abstain / n, 4),
        "unnecessary_strongest_use_rate": round(strongest_overuse / n, 4),
        "expensive_model_avoided_rate": round(expensive_avoided / n, 4),
        "explanation_completeness_rate": round(expl_ok / expl_checked, 4) if expl_checked else None,
    }


def _explanation_complete(rec: Dict[str, Any], all_models: set) -> bool:
    elig = set(rec["eligible"])
    elim = {e["model"] for e in rec["eliminated"]}
    if elig | elim != all_models:
        return False
    for e in rec["eliminated"]:
        if not e.get("reason") or not e.get("provenance"):
            return False
    if not rec["abstained"]:
        scored_ids = [s["model"] for s in rec["scored"]]
        if set(scored_ids) != elig or (scored_ids and rec["selected"] != scored_ids[0]):
            return False
        if rec["fallback_chain"] != scored_ids[1:]:
            return False
    return True


def commercial_vs_baseline(arm_sel, base_sel, tasks, results,
                           arm_pf_cost=None) -> Dict[str, Any]:
    """Commercial comparison of an arm against a baseline (typically strongest-eligible B)."""
    arm_pf_cost = arm_pf_cost or {}
    tasks_by_id = {t["task_id"]: t for t in tasks}
    routed_away, away_no_quality_loss, quality_failures_introduced = 0, 0, 0
    arm_cost, base_cost, arm_lat, base_lat, both = 0.0, 0.0, 0.0, 0.0, 0
    materially_inferior = 0
    for tid in arm_sel:
        task = tasks_by_id[tid]
        elig = _eligible_actuals(task, results)
        a, b = arm_sel[tid], base_sel.get(tid, {})
        if a.get("abstained") or b.get("abstained"):
            continue
        ac, bc = a.get("selected"), b.get("selected")
        if ac not in elig or bc not in elig:
            continue
        both += 1
        ar, br = elig[ac], elig[bc]
        arm_cost += ar["cost_usd"] + arm_pf_cost.get(tid, 0.0)
        base_cost += br["cost_usd"]
        arm_lat += ar["latency_ms"]
        base_lat += br["latency_ms"]
        if ac != bc:
            routed_away += 1
            thr = task.get("min_acceptable_quality", 0.0)
            if ar["quality"] >= thr:
                away_no_quality_loss += 1
            if br["quality"] >= thr and ar["quality"] < thr:
                quality_failures_introduced += 1
            if br["quality"] - ar["quality"] > 0.15:
                materially_inferior += 1
    return {
        "n_compared": both,
        "pct_routed_away_from_strongest": round(100 * routed_away / both, 1) if both else None,
        "pct_routed_away_without_quality_loss": round(100 * away_no_quality_loss / routed_away, 1) if routed_away else None,
        "quality_failures_introduced": quality_failures_introduced,
        "materially_inferior_selections": materially_inferior,
        "cost_reduction_pct_vs_baseline": round(100 * (base_cost - arm_cost) / base_cost, 1) if base_cost else None,
        "latency_reduction_pct_vs_baseline": round(100 * (base_lat - arm_lat) / base_lat, 1) if base_lat else None,
    }
