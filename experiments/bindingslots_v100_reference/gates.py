#!/usr/bin/env python3
"""Frozen hard gates + mechanical verdict for the V100 reference-backend characterization (torch-free).

17 reliability/integrity gates (all deterministic). Operational latency/storage numbers are recorded as
CHARACTERIZATION only — no deployment ceiling is approved this phase, so the qualified verdict
``ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED`` is NEVER emitted. The verdict always co-emits
``KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE``, ``BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`` and
``KDA_VALIDATION_BLOCKED``.
"""
from __future__ import annotations

# frozen tolerance (mirrors preregistration.json)
WITHIN_T0_PP = 0.001            # 0.1 percentage point

ALWAYS = ["KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE",
          "BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
          "KDA_VALIDATION_BLOCKED"]

# The qualified verdict is structurally forbidden in this phase.
FORBIDDEN_VERDICT = "ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED"

ALLOWED_VERDICTS = {
    "ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED",
    "ALWAYS_VERIFY_RELIABILITY_GATE_FAILED",
    "EXTERNAL_VERIFICATION_INTEGRITY_FAILED",
    "EXTERNAL_VERIFICATION_PROTOCOL_VIOLATED",
    "EXTERNAL_VERIFICATION_RESULTS_INCONCLUSIVE",
    "EXTERNAL_VERIFICATION_RESOURCE_BLOCKED",
}


def aggregate(per_seed):
    tot = lambda arm, k: sum(s[arm][k] for s in per_seed)
    n = sum(s["n"] for s in per_seed)
    m0 = tot("M0", "correct")
    t0 = tot("T0", "correct")
    v_ret_correct = sum(s["V100"]["returned_correct"] for s in per_seed)
    v_returned = sum(s["V100"]["returned"] for s in per_seed)
    v_incorrect = sum(s["V100"]["incorrect_verified"] for s in per_seed)
    v_disagree = sum(s["V100"]["disagreements"] for s in per_seed)
    v_corr = sum(s["V100"]["corrections"] for s in per_seed)
    v_incorr_corr = sum(s["V100"]["incorrect_corrections"] for s in per_seed)
    v_abstain = sum(s["V100"]["abstain"] for s in per_seed)
    v_prov = sum(s["V100"]["provenance_complete"] for s in per_seed)
    v_reads = sum(s["V100"]["reads"] for s in per_seed)
    m0_failures = n - m0
    cats = {}
    for s in per_seed:
        for c, v in s["V100"]["categories"].items():
            cats[c] = cats.get(c, 0) + v
    f0 = {k: sum(s["F0"][k] for s in per_seed) for k in
          ("correct", "fallback_invoked", "rescued", "unnecessary", "incorrect_fallback", "abstain")}
    conf = {k: sum(s["F0"]["confusion"][k] for s in per_seed) for k in ("tp", "fp", "tn", "fn")}
    return {
        "n": n,
        "M0_accuracy": m0 / n, "T0_accuracy": t0 / n,
        "M0_failures": m0_failures,
        "V100_accuracy": v_ret_correct / n,
        "V100_returned": v_returned, "V100_answer_availability": v_returned / n,
        "V100_incorrect_verified": v_incorrect,
        "V100_disagreements": v_disagree, "V100_corrections": v_corr,
        "V100_incorrect_corrections": v_incorr_corr,
        "V100_abstain": v_abstain, "V100_abstention_rate": v_abstain / n,
        "V100_provenance_completeness": (v_prov / v_returned) if v_returned else 1.0,
        "V100_reads": v_reads, "V100_reads_equal_n": (v_reads == n),
        "V100_categories": cats,
        "F0": f0, "F0_confusion": conf,
        "F0_accuracy": f0["correct"] / n,
        "F0_recall": (conf["tp"] / (conf["tp"] + conf["fn"])) if (conf["tp"] + conf["fn"]) else 1.0,
        "F0_precision": (conf["tp"] / (conf["tp"] + conf["fp"])) if (conf["tp"] + conf["fp"]) else 1.0,
        "F0_confidently_wrong_missed": conf["fn"],
        "F0_incorrect_fallback_rate": f0["incorrect_fallback"] / n,
    }


def gates(agg, scenarios, repro_all_match, model_unchanged, eval_optimizer_steps):
    s = scenarios
    g = {
        "1_accuracy_within_0.1pp_of_T0": abs(agg["V100_accuracy"] - agg["T0_accuracy"]) <= WITHIN_T0_PP,
        "2_incorrect_verified_returns_zero": agg["V100_incorrect_verified"] == 0,
        "3_incorrect_corrections_zero": agg["V100_incorrect_corrections"] == 0,
        "4_all_disagreements_detected": agg["V100_disagreements"] == agg["M0_failures"],
        "5_all_disagreements_corrected": agg["V100_corrections"] == agg["V100_disagreements"],
        "6_provenance_completeness_100pct": agg["V100_provenance_completeness"] >= 1.0,
        "7_cross_session_leakage_zero": s.get("cross_session_leakage_count", 1) == 0 and s.get("cross_session_no_disclosure", False),
        "8_cross_tenant_leakage_zero": s.get("cross_tenant_leakage_count", 1) == 0 and s.get("cross_tenant_no_disclosure", False),
        "9_stale_returns_zero": bool(s.get("stale_record_abstains")),
        "10_expired_returns_zero": bool(s.get("expired_record_abstains")),
        "11_deleted_returns_zero": bool(s.get("deleted_record_abstains")),
        "12_incorrect_version_returns_zero": bool(s.get("incorrect_version_not_returned")) and bool(s.get("latest_version_selected")),
        "13_table_unavailable_abstains": bool(s.get("table_unavailable_abstains")),
        "14_injected_failures_fail_closed": bool(s.get("injected_read_failure_fails_closed")) and bool(s.get("injected_write_failure_fails_closed")),
        "15_no_model_state_change": bool(model_unchanged) and (eval_optimizer_steps == 0),
        "16_deterministic_replay_succeeds": bool(repro_all_match),
        "17_cleanup_zero_live_session_records": bool(s.get("cleanup_zero_live_rows")) and bool(s.get("cleanup_then_abstains")),
        "exactly_one_read_per_v100_query": agg["V100_reads_equal_n"],
    }
    g["all_pass"] = all(bool(v) for k, v in g.items() if k != "all_pass")
    return g


def verdict(agg, g, torch_available=True, reproduced=True):
    if not torch_available or not reproduced:
        return "EXTERNAL_VERIFICATION_RESOURCE_BLOCKED", list(ALWAYS)
    if g["all_pass"]:
        return "ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED", list(ALWAYS)

    reliability_gate = all(g[k] for k in (
        "1_accuracy_within_0.1pp_of_T0", "2_incorrect_verified_returns_zero",
        "3_incorrect_corrections_zero", "4_all_disagreements_detected",
        "5_all_disagreements_corrected", "6_provenance_completeness_100pct"))
    integrity_gate = all(g[k] for k in (
        "7_cross_session_leakage_zero", "8_cross_tenant_leakage_zero", "9_stale_returns_zero",
        "10_expired_returns_zero", "11_deleted_returns_zero", "12_incorrect_version_returns_zero",
        "13_table_unavailable_abstains", "14_injected_failures_fail_closed",
        "17_cleanup_zero_live_session_records"))
    protocol_gate = g["15_no_model_state_change"] and g["16_deterministic_replay_succeeds"] and g["exactly_one_read_per_v100_query"]

    if not protocol_gate:
        return "EXTERNAL_VERIFICATION_PROTOCOL_VIOLATED", list(ALWAYS)
    if not integrity_gate:
        return "EXTERNAL_VERIFICATION_INTEGRITY_FAILED", list(ALWAYS)
    if not reliability_gate:
        return "ALWAYS_VERIFY_RELIABILITY_GATE_FAILED", list(ALWAYS)
    return "EXTERNAL_VERIFICATION_RESULTS_INCONCLUSIVE", list(ALWAYS)


FROZEN_GATES = {"WITHIN_T0_PP": WITHIN_T0_PP,
                "forbidden_verdict_this_phase": FORBIDDEN_VERDICT,
                "hard_gate_count": 17}
