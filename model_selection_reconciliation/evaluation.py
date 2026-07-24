"""Comparative evaluation of Policies A / B / C (reconciliation workstream).

Reuses the frozen ground-truth world (`model_selection_experiment.simulator`) and the
frozen scorer (`.metrics`) READ-ONLY. Each policy is measured on BOTH objectives so
neither is judged only on the other's home metric:

  * utility-regret vs the utility-oracle        — Policy A's objective (soft utility);
  * sufficiency + cost-efficiency vs the cheapest TRUE-sufficient model — B/C's objective.

Plus Q̂ calibration (does the predicted floor track the true floor?), abstention/false-
rejection, tier routing, threshold sweep, evidence-regime sensitivity (cold/partial/
mature = stale→fresh evidence), and deterministic reproducibility. No new estimator,
threshold, or registry field is invented.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from model_selection_experiment import metrics as met
from model_selection_experiment import simulator as sim
from model_selection_reconciliation import variants as V

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "model_selection_experiment", "data")
REGIMES = ("cold", "partial", "mature")
Q_SWEEP = (None, 0.60, 0.70, 0.80, 0.90)   # None = task-native acceptable_quality_threshold


def _load():
    reg = json.load(open(os.path.join(_DATA, "registry_v1.json")))
    pol = json.load(open(os.path.join(_DATA, "policy_v1.json")))
    corpus = json.load(open(os.path.join(_DATA, "corpus_v1.json")))
    provs = sorted({(m["declared"].get("provider", {}) or {}).get("value")
                    if isinstance(m["declared"].get("provider"), dict)
                    else m["declared"].get("provider") for m in reg["models"].values()})
    return reg, pol, corpus, list(provs)


def _qmin(task, q_min):
    return q_min if q_min is not None else float(task["acceptable_quality_threshold"])


def _cheapest_true_sufficient(task, approved, qmin):
    elig = sim.eligible_set(task, approved)
    suff = [m for m in elig if sim.true_quality(m, task) >= qmin]
    if not suff:
        return None, None            # correct action is abstain
    best = min(suff, key=lambda m: sim.true_cost(m, task))
    return best, sim.true_cost(best, task)


def _run(variant, tasks, reg, ent, tel, pol, regime, q_min) -> Dict[str, Any]:
    approved = ent["approved_providers"]
    recs = {}
    floor_viol = 0            # selected but TRUE quality < qmin (sufficiency failure)
    false_rej = 0            # abstained but a TRUE-sufficient eligible model existed
    correct_abstain = 0
    cost_ratios = []         # selected_true_cost / cheapest_true_sufficient_cost (sufficient picks only)
    sel_costs, sel_lats = [], []
    acceptable = 0           # selected TRUE quality >= qmin
    tiers: Dict[str, int] = {}
    # calibration bookkeeping (Q̂ vs true, over eligible candidates the policy scored)
    q_gap_sum, q_gap_n, optimistic, pessimistic = 0.0, 0, 0, 0
    for task in tasks:
        rec = V.route_variant(variant, task, reg, ent, tel, pol, regime, q_min=q_min)
        recs[task["task_id"]] = rec
        qm = _qmin(task, q_min)
        _, cheap_cost = _cheapest_true_sufficient(task, approved, qm)
        # calibration over scored candidates (only B/C expose predicted per candidate cleanly)
        for c in rec.get("scored", []) + rec.get("eliminated_by_quality", []):
            mid = c["model"]; qhat = c.get("predicted_quality")
            if qhat is None:
                continue
            tq = sim.true_quality(mid, task)
            q_gap_sum += abs(qhat - tq); q_gap_n += 1
            if qhat >= qm and tq < qm:
                optimistic += 1
            elif qhat < qm and tq >= qm:
                pessimistic += 1
        if rec["abstained"]:
            if cheap_cost is None:
                correct_abstain += 1
            else:
                false_rej += 1
            continue
        sel = rec["selected"]
        tq = sim.true_quality(sel, task)
        tiers[sel] = tiers.get(sel, 0) + 1
        sel_costs.append(sim.true_cost(sel, task)); sel_lats.append(sim.true_latency_ms(sel, task))
        if tq >= qm:
            acceptable += 1
            if cheap_cost:
                cost_ratios.append(sim.true_cost(sel, task) / cheap_cost if cheap_cost > 0 else 1.0)
        else:
            floor_viol += 1
    n = len(tasks)
    base_metrics = met.score_records(recs, {"tasks": tasks}, approved)
    return {
        "utility_regret": base_metrics["mean_regret"],
        "constraint_violation_rate": base_metrics["constraint_violation_rate"],
        "abstention_rate": base_metrics["abstention_rate"],
        "floor_violation_rate": round(floor_viol / n, 4),          # selected but truly insufficient
        "false_rejection_rate": round(false_rej / n, 4),           # abstained when sufficient existed
        "correct_abstention_rate": round(correct_abstain / n, 4),
        "acceptable_quality_rate_at_qmin": round(acceptable / n, 4),
        "mean_selected_true_cost": round(sum(sel_costs) / len(sel_costs), 4) if sel_costs else None,
        "mean_selected_true_latency_ms": round(sum(sel_lats) / len(sel_lats), 1) if sel_lats else None,
        "cost_efficiency_ratio_vs_cheapest_sufficient": round(sum(cost_ratios) / len(cost_ratios), 4) if cost_ratios else None,
        "tier_routing": dict(sorted(tiers.items())),
        "qhat_mean_abs_gap_vs_true": round(q_gap_sum / q_gap_n, 4) if q_gap_n else None,
        "qhat_optimistic_miscal_rate": round(optimistic / q_gap_n, 4) if q_gap_n else None,   # Q̂>=Qmin but true<Qmin
        "qhat_pessimistic_miscal_rate": round(pessimistic / q_gap_n, 4) if q_gap_n else None, # Q̂<Qmin but true>=Qmin
    }


def run_evaluation() -> Dict[str, Any]:
    reg, pol, corpus, provs = _load()
    tasks = corpus["tasks"]
    ent = {"approved_providers": provs}
    out: Dict[str, Any] = {"regimes": list(REGIMES), "q_sweep": [str(q) for q in Q_SWEEP],
                           "n_tasks": len(tasks), "results": {}}
    for regime in REGIMES:
        tel = sim.telemetry_feed(regime)
        out["results"][regime] = {}
        for q in Q_SWEEP:
            key = "native" if q is None else f"{q:.2f}"
            out["results"][regime][key] = {v: _run(v, tasks, reg, ent, tel, pol, regime, q)
                                           for v in V.VARIANTS}
    return out


def reproducible() -> bool:
    a = json.dumps(run_evaluation(), sort_keys=True)
    b = json.dumps(run_evaluation(), sort_keys=True)
    return a == b


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2))
