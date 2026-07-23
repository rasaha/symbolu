"""Aggregate metrics over decision records, scored against ground truth.

All preflight/self-assessment costs are charged to the arm that used them
(arm G) before cost/latency metrics are computed.
"""

from __future__ import annotations

from typing import Any, Dict, List

import simulator as sim
from common import percentile

REQUIRED_RECORD_FIELDS = [
    "arm", "task_id", "selected", "abstained", "eligible", "eliminated",
    "scored", "fallback_chain",
]


def explanation_completeness(record: Dict[str, Any]) -> Dict[str, Any]:
    """Structural faithfulness check for a policy decision record (arms F/G).

    A record is complete iff:
      * all required fields present;
      * every non-eligible model appears in 'eliminated' with a reason+provenance;
      * eligible + eliminated partition the full model set (no silent drops);
      * if not abstained, selected is in eligible and is the top-ranked scored model;
      * fallback_chain equals the remaining scored models in order.
    """
    issues: List[str] = []
    for f in REQUIRED_RECORD_FIELDS:
        if f not in record:
            issues.append(f"missing field '{f}'")
    if issues:
        return {"complete": False, "issues": issues}

    all_models = set(sim.MODEL_IDS)
    elig = set(record["eligible"])
    elim_models = [e["model"] for e in record["eliminated"]]
    elim = set(elim_models)

    # partition check
    if elig | elim != all_models:
        issues.append("eligible + eliminated do not cover all models")
    if elig & elim:
        issues.append("model appears both eligible and eliminated")
    if len(elim_models) != len(elim):
        issues.append("duplicate eliminated entries")
    for e in record["eliminated"]:
        if not e.get("reason") or not e.get("provenance"):
            issues.append(f"elimination of {e.get('model')} lacks reason/provenance")

    if not record["abstained"]:
        if record["selected"] not in elig:
            issues.append("selected model not in eligible set")
        scored_ids = [s["model"] for s in record["scored"]]
        if set(scored_ids) != elig:
            issues.append("scored set != eligible set")
        if scored_ids and record["selected"] != scored_ids[0]:
            issues.append("selected is not the top-ranked scored model")
        if record["fallback_chain"] != scored_ids[1:]:
            issues.append("fallback_chain != remaining scored order")
    else:
        if record["selected"] is not None:
            issues.append("abstained record has a non-null selection")
        if not record["abstain_reason"]:
            issues.append("abstained record lacks abstain_reason")

    return {"complete": not issues, "issues": issues}


def _effective_cost_latency(record: Dict[str, Any], task: Dict[str, Any]):
    """Achieved cost/latency of the selection, charging preflight to the arm."""
    if record["abstained"] or record["selected"] is None:
        return 0.0, 0.0
    mid = record["selected"]
    cost = sim.true_cost(mid, task) + record.get("preflight_cost", 0.0)
    lat = sim.true_latency_ms(mid, task) + record.get("preflight_latency_ms", 0.0)
    return cost, lat


def score_records(records_by_task: Dict[str, Dict[str, Any]], corpus: Dict[str, Any],
                  approved_providers: List[str]) -> Dict[str, Any]:
    """Score one arm's records (task_id -> record) into aggregate metrics."""
    tasks = {t["task_id"]: t for t in corpus["tasks"]}
    n = len(records_by_task)

    regrets, violations, threshold_success, completions = [], 0, 0, 0
    costs_success, latencies, fallback_used, abstentions = [], [], 0, 0
    strongest_overuse, expl_complete, expl_checked = 0, 0, 0
    empty_sets_handled = 0
    cold_ok = 0

    for tid, rec in records_by_task.items():
        task = tasks[tid]
        rq = sim.regret_for_choice(task, rec["selected"], approved_providers, rec["abstained"])
        regrets.append(rq["regret"])
        if rq["violated"]:
            violations += 1
        if rq["empty_eligible"] and rec["abstained"]:
            empty_sets_handled += 1
        if rec["abstained"]:
            abstentions += 1
        # completion / quality-threshold success (must be eligible & meet bar)
        if not rec["abstained"] and not rq["violated"]:
            tq = sim.true_quality(rec["selected"], task)
            completions += 1
            if tq >= task["acceptable_quality_threshold"]:
                threshold_success += 1
                c, l = _effective_cost_latency(rec, task)
                costs_success.append(c)
        # latency for every executed pick (non-abstain, non-violating)
        if not rec["abstained"] and not rq["violated"]:
            _, l = _effective_cost_latency(rec, task)
            latencies.append(l)
        if rec.get("fallback_chain"):
            fallback_used += 1
        # unnecessary strongest-model usage: picked the most expensive eligible model
        # while a cheaper eligible model would have met the quality threshold.
        if not rec["abstained"] and not rq["violated"]:
            orc = sim.oracle(task, approved_providers)
            if orc["eligible"]:
                most_expensive = max(orc["eligible"], key=lambda m: sim.true_cost(m, task))
                cheaper_ok = any(
                    sim.true_cost(m, task) < sim.true_cost(rec["selected"], task)
                    and sim.true_quality(m, task) >= task["acceptable_quality_threshold"]
                    for m in orc["eligible"])
                if rec["selected"] == most_expensive and cheaper_ok:
                    strongest_overuse += 1
        # explanation completeness (policy arms carry full records)
        if rec["arm"] in ("F", "G"):
            expl_checked += 1
            if explanation_completeness(rec)["complete"]:
                expl_complete += 1

    return {
        "n_tasks": n,
        "mean_regret": round(sum(regrets) / n, 4),
        "p95_regret": round(percentile(regrets, 0.95), 4),
        "constraint_violation_rate": round(violations / n, 4),
        "completion_rate": round(completions / n, 4),
        "quality_threshold_success_rate": round(threshold_success / n, 4),
        "mean_cost_per_successful_task": round(sum(costs_success) / len(costs_success), 4) if costs_success else None,
        "p50_latency_ms": round(percentile(latencies, 0.50), 1) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 0.95), 1) if latencies else None,
        "fallback_offered_rate": round(fallback_used / n, 4),
        "abstention_rate": round(abstentions / n, 4),
        "empty_eligible_handled": empty_sets_handled,
        "unnecessary_strongest_use_rate": round(strongest_overuse / n, 4),
        "explanation_completeness_rate": round(expl_complete / expl_checked, 4) if expl_checked else None,
    }
