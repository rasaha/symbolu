"""ACP V2 cloud shadow benchmark harness (§9, §12, §13).

Runs the whole cloud corpus through the shadow adapter (which reuses the frozen
ACP core unchanged + the real ``cloud_controller`` logic), computes the §12
metrics, checks determinism and the §13 safety invariants, and writes
``robotics_reliability_bench/results/acp_cloud_results.json``.

Shadow-only. Never actuates. Deterministic. Stdlib-only.

Run: ``python -m robotics_reliability_bench.acp_cloud.run_cloud_bench``
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List

from symbolu_robotics.autonomous_control_plane.cloud import (
    AuthorizationVerdict,
    CloudShadowAdapter,
    CombinedOutcome,
    is_permissive,
)
from symbolu_robotics.autonomous_control_plane.cloud.envelopes import CloudValidity
from robotics_reliability_bench.acp_cloud.corpus import (
    NOW_S,
    build_corpus,
    provenance_counts,
)

# Silence the real cloud_controller loggers — they intentionally warn on policy
# denials, which are expected corpus outcomes, not errors.
logging.disable(logging.CRITICAL)

_RESULTS = os.path.join(os.path.dirname(__file__), "..", "results",
                        "acp_cloud_results.json")


def _run_once(record_latency: bool):
    """Run the whole corpus once. Return (per_scenario, latencies_ms, adapter)."""
    adapter = CloudShadowAdapter(enabled=True)
    corpus = build_corpus()
    per_scenario: List[dict] = []
    latencies_ms: List[float] = []

    for s in corpus:
        t0 = time.perf_counter()
        result = adapter.observe(
            decision_id=s.scenario_id, world=s.world,
            candidates=list(s.candidates), now_s=NOW_S,
            freshness_s=s.freshness_s, authorization=s.authorization)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if record_latency:
            latencies_ms.append(dt_ms)

        rec = result.cloud_recommendation
        comb = result.composition.combined.value if result.composition else None

        # Commit-revalidation for TOCTOU scenarios.
        revalidation = None
        if (s.drift_world is not None or s.drift_manifest_candidate is not None):
            decided = s.candidates[0]  # what ACP decided on
            current_cand = s.drift_manifest_candidate  # mutated at commit (or None)
            still_valid, reason = adapter.commit_revalidate(
                decision_id=s.scenario_id, selected=decided,
                world_at_decision=s.world, constraint_set_version="cs-1",
                current_world=(s.drift_world or s.world),
                current_constraint_set_version="cs-1",
                issued_time_s=NOW_S, now_s=NOW_S + 1.0,
                current_candidate=current_cand)
            revalidation = {"still_valid": still_valid, "reason": reason}

        # Evidence validity (first candidate) + fail-closed flag.
        first_ev = next(iter(result.evidence.values()), None)
        validity = first_ev.validity.value if first_ev else CloudValidity.MISSING.value

        per_scenario.append({
            "scenario_id": s.scenario_id,
            "provenance": s.provenance,
            "acp_decision": result.acp_decision.value,
            "cloud_recommendation": rec.value,
            "permissive": is_permissive(rec),
            "authorization": s.authorization.value if s.authorization else None,
            "combined_outcome": comb,
            "evidence_validity": validity,
            "reason_codes": list(result.record.reason_codes),
            "shadow_only": result.record.shadow_only,
            "shadow_error": result.record.shadow_error,
            "expect_permissive": s.expect_permissive,
            "expect_combined": s.expect_combined,
            "permissive_match": is_permissive(rec) == s.expect_permissive,
            "combined_match": (s.expect_combined is None
                               or comb == s.expect_combined),
            "revalidation": revalidation,
        })
    return per_scenario, latencies_ms, adapter


def _content_signature(per_scenario: List[dict]) -> List[dict]:
    """Deterministic content view (excludes latency; latency isn't stored here)."""
    keys = ("scenario_id", "acp_decision", "cloud_recommendation", "permissive",
            "combined_outcome", "evidence_validity", "reason_codes",
            "shadow_only", "shadow_error", "revalidation")
    return [{k: r[k] for k in keys} for r in per_scenario]


def main() -> dict:
    # Warm up lazy imports (real cloud_controller modules) so measured latency
    # reflects steady state, not one-time import cost. Then two independent runs
    # to prove determinism; latency is taken from the first measured run.
    run_b, _, _ = _run_once(record_latency=False)          # warmup + run B
    run_a, latencies, adapter = _run_once(record_latency=True)
    deterministic = _content_signature(run_a) == _content_signature(run_b)

    n = len(run_a)
    # ---- cloud shadow metrics (§12) ----
    decisions: Dict[str, int] = {}
    recs: Dict[str, int] = {}
    for r in run_a:
        decisions[r["acp_decision"]] = decisions.get(r["acp_decision"], 0) + 1
        recs[r["cloud_recommendation"]] = recs.get(r["cloud_recommendation"], 0) + 1
    fail_closed = [r for r in run_a
                   if r["evidence_validity"] != CloudValidity.VALID.value]
    fail_closed_all_hold = all(not r["permissive"] for r in fail_closed)

    # ---- ActionGate x ACP composition metrics (§12) ----
    combos: Dict[str, int] = {}
    for r in run_a:
        if r["combined_outcome"] is not None:
            combos[r["combined_outcome"]] = combos.get(r["combined_outcome"], 0) + 1
    acp_decisive = [r for r in run_a
                    if r["combined_outcome"] == CombinedOutcome.HELD_BY_ACP.value]
    ag_blocked = [r for r in run_a
                  if r["combined_outcome"]
                  == CombinedOutcome.BLOCKED_BY_AUTHORIZATION.value]
    both_pass = [r for r in run_a
                 if r["combined_outcome"] == CombinedOutcome.PROCEED.value]

    # ---- §13 safety invariants ----
    # I1: an ActionGate DENY is never composed to PROCEED.
    inv_deny_never_proceed = all(
        r["combined_outcome"] != CombinedOutcome.PROCEED.value
        for r in run_a if r["authorization"] == AuthorizationVerdict.DENY.value)
    # I2: ACP hold never proceeds regardless of authorization.
    inv_hold_never_proceed = all(
        r["combined_outcome"] != CombinedOutcome.PROCEED.value
        for r in run_a if not r["permissive"])
    # I3: PROCEED requires BOTH an authorizing verdict AND a permissive ACP.
    inv_proceed_needs_both = all(
        (r["authorization"] in (AuthorizationVerdict.ALLOW.value,
                                AuthorizationVerdict.ALLOW_WITH_CONSTRAINTS.value)
         and r["permissive"])
        for r in both_pass)
    # I4: every record is shadow-only; no actuation.
    inv_all_shadow = all(r["shadow_only"] for r in run_a)
    # I5: no uncontained shadow error.
    inv_no_error = all(not r["shadow_error"] for r in run_a)
    # I6: the two decisive boundary scenarios resolve as designed.
    by_id = {r["scenario_id"]: r for r in run_a}
    inv_boundary = (
        by_id["ag_allows_acp_holds"]["combined_outcome"]
        == CombinedOutcome.HELD_BY_ACP.value
        and by_id["ag_denies_acp_safe"]["combined_outcome"]
        == CombinedOutcome.BLOCKED_BY_AUTHORIZATION.value)
    # I7: commit revalidation rejects both drift scenarios.
    inv_reval = all(
        r["revalidation"] is None or r["revalidation"]["still_valid"] is False
        for r in run_a if r["scenario_id"]
        in ("state_drift", "modified_manifest_after_eval"))

    # ---- correctness vs preregistered expectations ----
    perm_mismatch = [r["scenario_id"] for r in run_a if not r["permissive_match"]]
    comb_mismatch = [r["scenario_id"] for r in run_a if not r["combined_match"]]

    # ---- latency ----
    latencies.sort()
    lat = {
        "mean_ms": round(sum(latencies) / len(latencies), 4),
        "p95_ms": round(latencies[int(0.95 * (len(latencies) - 1))], 4),
        "max_ms": round(latencies[-1], 4),
    }

    results = {
        "meta": {
            "milestone": "ACP V2 cross-domain (cloud/K8s adapter)",
            "shadow_only": True,
            "actuation": False,
            "n_scenarios": n,
            "provenance_counts": provenance_counts(build_corpus()),
            "frozen_core_reused_unchanged": [
                "identity.identity", "identity.normalize_float",
                "constraints.ConstraintResult", "constraints.ConstraintKind",
                "action_selection.filter_admissible",
                "action_selection.LexicographicActionSelector",
                "decision_trace.DecisionTrace",
                "envelopes.ActionDecision",
                "authorization.ReferenceCommitRevalidator",
                "authorization.ControlAuthorization",
                "errors.ACPError",
            ],
            "real_cloud_controller_modules": [
                "cloud_controller.action.readiness.ReadinessChecker",
                "cloud_controller.action.policy.PolicyEngine",
                "cloud_controller.action.policy.DeploymentPolicy",
                "cloud_controller.recommend.safety.SafetyBounds",
            ],
        },
        "cloud_shadow_metrics": {
            "decision_distribution": decisions,
            "recommendation_distribution": recs,
            "fail_closed_count": len(fail_closed),
            "fail_closed_all_hold": fail_closed_all_hold,
        },
        "composition_metrics": {
            "combined_distribution": combos,
            "acp_decisive_count": len(acp_decisive),
            "acp_decisive_scenarios": [r["scenario_id"] for r in acp_decisive],
            "authorization_blocked_count": len(ag_blocked),
            "authorization_blocked_scenarios": [r["scenario_id"] for r in ag_blocked],
            "both_layers_proceed_count": len(both_pass),
        },
        "safety_invariants": {
            "I1_deny_never_proceed": inv_deny_never_proceed,
            "I2_acp_hold_never_proceed": inv_hold_never_proceed,
            "I3_proceed_requires_both_layers": inv_proceed_needs_both,
            "I4_all_records_shadow_only": inv_all_shadow,
            "I5_no_uncontained_shadow_error": inv_no_error,
            "I6_decisive_boundary_scenarios": inv_boundary,
            "I7_commit_revalidation_rejects_drift": inv_reval,
        },
        "determinism": {
            "rerun_identity": deterministic,
            "sink_seen": adapter.sink.seen,
            "sink_dropped": adapter.sink.dropped,
        },
        "correctness": {
            "permissive_mismatches": perm_mismatch,
            "combined_mismatches": comb_mismatch,
            "all_expectations_met": not perm_mismatch and not comb_mismatch,
        },
        "latency": lat,
        "per_scenario": run_a,
    }

    os.makedirs(os.path.dirname(_RESULTS), exist_ok=True)
    with open(_RESULTS, "w") as fh:
        json.dump(results, fh, indent=2, sort_keys=True)
    return results


if __name__ == "__main__":
    out = main()
    inv = out["safety_invariants"]
    print("ACP V2 cloud shadow benchmark")
    print(f"  scenarios: {out['meta']['n_scenarios']}  "
          f"provenance: {out['meta']['provenance_counts']}")
    print(f"  decisions: {out['cloud_shadow_metrics']['decision_distribution']}")
    print(f"  combined:  {out['composition_metrics']['combined_distribution']}")
    print(f"  ACP-decisive (HELD_BY_ACP): "
          f"{out['composition_metrics']['acp_decisive_scenarios']}")
    print(f"  AG-blocked: "
          f"{out['composition_metrics']['authorization_blocked_scenarios']}")
    print(f"  invariants all pass: {all(inv.values())}  -> {inv}")
    print(f"  determinism: {out['determinism']}")
    print(f"  correctness: {out['correctness']['all_expectations_met']}")
    print(f"  latency: {out['latency']}")
