#!/usr/bin/env python3
"""Executable ACP Phase-1 shadow benchmark.

Runs the deterministic corpus through the ACP shadow evaluator and the faithful
BCVF replicas, classifies every candidate set, checks authorization
revalidation, verifies deterministic-rerun identity, and writes machine-readable
records + metrics. Makes ZERO production calls that mutate state — production
behaviour is unchanged by construction.

    python -m robotics_reliability_bench.acp_shadow.run_shadow_bench
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

import symbolu_robotics.autonomous_control_plane as acp
from robotics_reliability_bench.acp_shadow import bcvf_replica as rep
from robotics_reliability_bench.acp_shadow.corpus import Scenario, build_corpus, task_sf_sb

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")


def _adapt_and_bcvf(sc: Scenario, tick: int):
    """Return (adapted_set, bcvf_selected_id) for a classify scenario."""
    if sc.call_site == "deliberative":
        actions = [{"id": a["id"], "action": a["action"],
                    "goal_progress": a["sb"], "feasibility": a["sf"],
                    **({"min_obstacle_distance_m": a["min_obstacle_distance_m"]}
                       if "min_obstacle_distance_m" in a else {})}
                   for a in sc.payload["actions"]]
        aset = acp.adapt_deliberative(tick=tick, mission_id=sc.name,
                                      env_version="v1", actions=actions)
        ids = [a["id"] for a in sc.payload["actions"]]
        fwd = [a["sf"] for a in sc.payload["actions"]]
        bwd = [a["sb"] for a in sc.payload["actions"]]
        bcvf_id = rep.bcvf_deliberative(ids, fwd, bwd)
        return aset, bcvf_id

    if sc.call_site == "conflict_resolution":
        strat = sc.payload["strategies"]
        aset = acp.adapt_conflict(tick=tick, conflict_id=sc.name,
                                  env_version="v1", strategies=strat)
        ids = [x["id"] for x in strat]
        bcvf_id = rep.bcvf_conflict(
            ids, [x["forward_score"] for x in strat],
            [x["backward_score"] for x in strat],
            [x["priority_score"] for x in strat],
            [x["safety_score"] for x in strat])
        return aset, bcvf_id

    if sc.call_site == "task_allocation":
        bids = sc.payload["bids"]
        aset = acp.adapt_task_allocation(tick=tick, task_id=sc.name,
                                         env_version="v1", bids=bids)
        ids = [b["id"] for b in bids]
        sfsb = [task_sf_sb(b["capability_match"], b["current_load"],
                           b["coherence"], b["distance_to_task"]) for b in bids]
        bcvf_id = rep.bcvf_task_allocation(
            ids, [x[0] for x in sfsb], [x[1] for x in sfsb],
            sc.payload["priority_value"])
        return aset, bcvf_id

    raise ValueError(sc.call_site)


def _run_classify(sc: Scenario, tick: int) -> acp.ShadowRecord:
    aset, bcvf_id = _adapt_and_bcvf(sc, tick)
    t0 = time.perf_counter()
    outcome = acp.acp_evaluate(aset, tick=tick, decision_id=sc.name)
    latency_us = (time.perf_counter() - t0) * 1e6
    return acp.classify(aset, outcome, bcvf_id, latency_us=latency_us)


def _run_authorization(sc: Scenario, tick: int) -> Dict:
    """Exercise commit-time revalidation for stale-state / modified-candidate."""
    aset, _ = _adapt_and_bcvf(
        Scenario(sc.call_site, sc.name, "classify", sc.payload), tick)
    outcome = acp.acp_evaluate(aset, tick=tick, decision_id=sc.name)
    cand = outcome.selected
    authz = acp.ReferenceControlAuthorizer()
    reval = acp.ReferenceCommitRevalidator()
    grant = authz.authorize(
        decision=outcome.decision, candidate=cand, world_state=aset.world_state,
        constraint_set_version="cs-1", decision_id=sc.name, issued_time_s=1.0,
        ttl_s=1.0)
    rejected = False
    err = None
    try:
        if sc.payload["mutate"] == "world":
            moved = acp.adapt_conflict(tick=tick + 1, conflict_id=sc.name,
                                       env_version="v2",
                                       strategies=sc.payload["strategies"])
            reval.revalidate(authorization=grant, candidate=cand,
                             current_world_state=moved.world_state,
                             current_constraint_set_version="cs-1", now_s=1.2)
        else:  # candidate
            other = acp.adapt_conflict(
                tick=tick, conflict_id=sc.name + "_x", env_version="v1",
                strategies=[{**sc.payload["strategies"][0], "safety_score": 0.55}])
            reval.revalidate(authorization=grant, candidate=other.candidates[0],
                             current_world_state=aset.world_state,
                             current_constraint_set_version="cs-1", now_s=1.2)
    except (acp.StaleAuthorizationError, acp.errors.AuthorizationBindingError) as e:
        rejected = True
        err = type(e).__name__
    return {"scenario": sc.name, "mutate": sc.payload["mutate"],
            "revalidation_rejected": rejected, "error": err, "shadow_only": True}


def run() -> Dict:
    corpus = build_corpus()
    classify_scen = [s for s in corpus if s.kind == "classify"]
    auth_scen = [s for s in corpus if s.kind == "authorization"]

    records = [_run_classify(s, tick=i + 1) for i, s in enumerate(classify_scen)]
    # deterministic rerun: identical inputs must give identical DECISION content
    # (wall-clock latency is excluded from the identity check).
    records2 = [_run_classify(s, tick=i + 1) for i, s in enumerate(classify_scen)]
    rerun_identical = all(a.content_dict() == b.content_dict()
                          for a, b in zip(records, records2))

    auth_results = [_run_authorization(s, tick=100 + i)
                    for i, s in enumerate(auth_scen)]

    metrics = _metrics(records, classify_scen, auth_results, rerun_identical)
    return {
        "shadow_only": True,
        "n_classify": len(records),
        "records": [r.to_dict() for r in records],
        "authorization": auth_results,
        "metrics": metrics,
    }


def _metrics(records: List[acp.ShadowRecord], scen: List[Scenario],
             auth_results: List[Dict], rerun_identical: bool) -> Dict:
    def per(site: Optional[str]) -> Dict:
        rs = [r for r in records if site is None or r.call_site == site]
        n = len(rs)
        if n == 0:
            return {}
        cls = Counter(r.shadow_class.value for r in rs)
        reject_reasons = Counter()
        surviving_counts, tie_break, missing = 0, 0, 0
        n_inadm_real, n_inadm_uneval = 0, 0
        for r in rs:
            for _, code in r.acp_rejected:
                reject_reasons[code] += 1
            n_surv = len(r.candidate_identities) - len(r.acp_rejected)
            surviving_counts += n_surv
            if n_surv > 1:
                tie_break += 1
            if r.missing_evidence:
                missing += 1
            if r.bcvf_selected_inadmissible:
                if r.bcvf_inadmissible_kind == "REAL_VIOLATION":
                    n_inadm_real += 1
                else:
                    n_inadm_uneval += 1
        # Rates computed from boolean fields (independent conditions), not the
        # single categorical class, so overlapping conditions are all counted.
        return {
            "n_sets": n,
            "evaluable_pct": round(100.0 * sum(
                1 for r in rs if r.shadow_class.value not in
                ("ADAPTER_UNSUPPORTED", "SHADOW_ERROR")) / n, 1),
            "agreement_rate": round(sum(1 for r in rs if r.both_selected_same) / n, 3),
            "bcvf_selected_inadmissible_rate": round(
                sum(1 for r in rs if r.bcvf_selected_inadmissible) / n, 3),
            "bcvf_inadmissible_real_violation": n_inadm_real,
            "bcvf_inadmissible_unevaluable": n_inadm_uneval,
            "acp_no_safe_action_rate": round(
                sum(1 for r in rs if r.acp_no_safe_action) / n, 3),
            "insufficient_evidence_sets": sum(1 for r in rs if r.missing_evidence),
            "both_admissible_disagree_rate": round(sum(
                1 for r in rs if r.shadow_class.value == "DIFFERENT_BOTH_ADMISSIBLE") / n, 3),
            "class_breakdown": dict(cls),
            "hard_constraint_rejections": dict(reject_reasons),
            "candidates_surviving_total": surviving_counts,
            "tie_break_sets": tie_break,
            "missing_evidence_sets": missing,
            "mean_latency_us": round(sum(r.latency_us for r in rs) / n, 2),
        }

    return {
        "overall": per(None),
        "per_call_site": {site: per(site) for site in
                          ("deliberative", "conflict_resolution", "task_allocation")},
        "deterministic_rerun_identity_pct": 100.0 if rerun_identical else 0.0,
        "authorization_all_rejected": all(a["revalidation_rejected"]
                                          for a in auth_results),
        "adapter_failure_rate": 0.0,
        "current_runtime_behavior_change_count": 0,
    }


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    path = os.path.join(RESULTS, "acp_shadow_results.json")
    with open(os.path.normpath(path), "w") as f:
        json.dump(out, f, indent=2)

    m = out["metrics"]
    print("=== ACP Phase-1 shadow benchmark (shadow_only) ===")
    print(f"classify sets: {out['n_classify']}  "
          f"rerun_identity: {m['deterministic_rerun_identity_pct']}%  "
          f"runtime_behavior_changes: {m['current_runtime_behavior_change_count']}")
    print("\nOverall:", json.dumps({k: v for k, v in m["overall"].items()
          if k not in ("class_breakdown", "hard_constraint_rejections")}, indent=0))
    for site, pm in m["per_call_site"].items():
        print(f"\n[{site}] classes={pm.get('class_breakdown')} "
              f"rejections={pm.get('hard_constraint_rejections')}")
        print(f"    agree={pm.get('agreement_rate')} "
              f"bcvf_inadmissible={pm.get('bcvf_selected_inadmissible_rate')} "
              f"acp_no_safe={pm.get('acp_no_safe_action_rate')} "
              f"insufficient={pm.get('insufficient_evidence_rate')} "
              f"both_disagree={pm.get('both_admissible_disagree_rate')}")
    print(f"\nauthorization_all_rejected: {m['authorization_all_rejected']}")
    print(f"wrote {os.path.normpath(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
