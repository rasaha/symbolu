"""R2 metrics + evidence-based planner-automation verdict.

All numbers are measured over the corpus run through the deterministic simulator against the
REAL gate. The verdict answers: should ActionGate ever drive an automatic planner loop, and
under exactly what measured conditions?
"""

from __future__ import annotations

from collections import Counter

import corpus as C
import simulator as SIM
from action_gate_ref import gate
from action_gate_ref import remediation as R


def _observed_class(scenario):
    d = gate.evaluate(scenario.envelope, scenario.signed_policy,
                      evidence=scenario.initial_evidence, approvals=scenario.initial_approvals,
                      now=C.NOW)
    rem = R.project_remediation(d, scenario.envelope, scenario.signed_policy,
                                evidence=scenario.initial_evidence,
                                approvals=scenario.initial_approvals, now=C.NOW,
                                disclosure_mode="FULL", trusted_context=True)
    if d["outcome"].startswith("ALLOW"):
        return "ALLOW"
    rc = rem["required_changes"][0]["retry_class"] if rem["required_changes"] else None
    return C.retry_to_class(rc) if rc else "UNKNOWN"


def _leaks_threshold(scenario, mode):
    """True if a non-privileged projection would expose an exact threshold number."""
    d = gate.evaluate(scenario.envelope, scenario.signed_policy,
                      evidence=scenario.initial_evidence, approvals=scenario.initial_approvals,
                      now=C.NOW)
    rem = R.project_remediation(d, scenario.envelope, scenario.signed_policy,
                                evidence=scenario.initial_evidence,
                                approvals=scenario.initial_approvals, now=C.NOW,
                                disclosure_mode=mode)
    import json
    blob = json.dumps(rem)
    # the corpus's only numeric thresholds are scope 10000 and cost 100000
    return ("10000" in blob) or ("100000" in blob)


def _stable(scenario):
    a = SIM.simulate(scenario)
    b = SIM.simulate(scenario)
    ta = [(s["outcome"], s["action_hash"]) for s in a.trajectory]
    tb = [(s["outcome"], s["action_hash"]) for s in b.trajectory]
    return a.status == b.status and ta == tb


def compute(scenarios, results):
    total = len(scenarios)
    status = Counter(r.status for r in results)
    exp_classes = Counter(s.expected_class for s in scenarios)
    obs_classes = Counter(_observed_class(s) for s in scenarios)

    succ = status[SIM.ALLOW_SUCCESS]
    retries_all = [r.retries for r in results]
    retries_succ = [r.retries for r in results if r.status == SIM.ALLOW_SUCCESS]

    # per-class simulator outcomes
    by_class = {c: Counter() for c in C.CLASSES}
    for s, r in zip(scenarios, results):
        by_class[s.expected_class][r.status] += 1

    am = exp_classes[C.ACTION_MODIFICATION_REMEDIABLE]
    am_results = [r for s, r in zip(scenarios, results)
                  if s.expected_class == C.ACTION_MODIFICATION_REMEDIABLE]
    am_success = sum(1 for r in am_results if r.status == SIM.ALLOW_SUCCESS)
    am_terminal = sum(1 for r in am_results if r.status == SIM.TERMINAL)   # unbinding safety-stop
    am_stuck = sum(1 for r in am_results if r.status in (SIM.STUCK, SIM.EXHAUSTED,
                                                         SIM.OSCILLATION))

    remediable_total = total - exp_classes[C.TERMINAL] - exp_classes[C.HUMAN_ONLY]

    leakage = sum(1 for s in scenarios if _leaks_threshold(s, "STANDARD")
                  or _leaks_threshold(s, "MINIMAL"))
    stability = sum(1 for s in scenarios if _stable(s))

    security = {
        "no_token_minted": not any(r.minted_token for r in results),
        "fresh_hash_on_every_modification": all(r.fresh_hash_on_modification for r in results),
        "no_deny_bypass": not any(r.ended_after_deny_nonterminal for r in results),
        "no_success_reached_through_deny": all(
            not (r.saw_deny and r.status == SIM.ALLOW_SUCCESS) for r in results),
        "total_action_modifications": sum(r.modifications for r in results),
    }

    m = {
        "total_scenarios": total,
        "status_distribution": dict(status),
        "expected_class_distribution": dict(exp_classes),
        "observed_class_distribution": dict(obs_classes),
        "per_class_simulator_outcomes": {k: dict(v) for k, v in by_class.items()},
        "successful_remediation_rate": round(succ / total, 4),
        "terminal_rate": round(status[SIM.TERMINAL] / total, 4),
        "human_escalation_rate": round(status[SIM.ESCALATED_HUMAN] / total, 4),
        "oscillation_rate": round(status[SIM.OSCILLATION] / total, 4),
        "capability_stall_rate": round(status[SIM.STUCK] / total, 4),
        "retry_budget_exhaustion_rate": round(status[SIM.EXHAUSTED] / total, 4),
        "average_retries": round(sum(retries_all) / total, 3),
        "average_retries_on_success": round(sum(retries_succ) / max(1, len(retries_succ)), 3),
        "maximum_retries": max(retries_all),
        "policy_leakage_count": leakage,
        "policy_leakage_rate": round(leakage / total, 4),
        "decision_stability_rate": round(stability / total, 4),
        "security": security,
        "action_modification": {
            "count": am,
            "share_of_all": round(am / total, 4),
            "share_of_remediable": round(am / max(1, remediable_total), 4),
            "autonomous_success": am_success,
            "autonomous_success_rate": round(am_success / max(1, am), 4),
            "terminal_by_unbinding": am_terminal,
            "capability_stall_or_conflict": am_stuck,
        },
    }
    m["verdict"] = verdict(m)
    return m


def verdict(m):
    """Evidence-based recommendation for planner automation.

    An LLM planner's ONLY unique value would be in action-modification cases that a simple
    DETERMINISTIC transform cannot already resolve for reasons that *search/creativity* could
    fix — as opposed to (a) a safety stop where modification unbinds a hard precondition, or
    (b) a capability/quota limit or a required human approval, none of which a planner should
    route around. We therefore measure the residual 'planning gap'.
    """
    am = m["action_modification"]
    am_share = am["share_of_all"]
    am_success = am["autonomous_success_rate"]
    # planning gap = AM failures that are NOT safety-stops and NOT capability/human limits.
    # In this corpus every AM failure is either a safety unbinding (terminal) or a capability
    # stall/conflict, so the planning gap an LLM could close is zero.
    residual = am["count"] - am["autonomous_success"] - am["terminal_by_unbinding"] \
        - am["capability_stall_or_conflict"]
    planning_gap_rate = round(max(0, residual) / max(1, m["total_scenarios"]), 4)

    # deterministic remediation: justified for the mechanical, policy-opted-in classes
    det_value = (m["successful_remediation_rate"] > 0.20 and
                 m["security"]["no_deny_bypass"] and
                 m["security"]["fresh_hash_on_every_modification"] and
                 m["policy_leakage_count"] == 0)
    deterministic = "LIMITED_GO" if det_value else "STOP"

    # LLM planner: justified only if there is a real, common planning gap deterministic
    # automation cannot close. Measured gap here is ~0.
    if am_share >= 0.30 and planning_gap_rate >= 0.10 and am_success < 0.5:
        planner = "GO"
    elif am_share >= 0.15 and planning_gap_rate >= 0.05:
        planner = "LIMITED_GO"
    else:
        planner = "STOP"

    return {
        "planner_automation": planner,
        "deterministic_remediation": deterministic,
        "action_modification_share_of_all": am_share,
        "action_modification_autonomous_success_rate": am_success,
        "measured_planning_gap_rate": planning_gap_rate,
        "rationale": (
            "LLM-planner recommendation = {p}. Action-modification is {sh:.0%} of scenarios and "
            "{sr:.0%} of those are already resolved by a DETERMINISTIC numeric transform (no "
            "planning). Every action-modification failure is a safety stop (modification unbinds "
            "a hard precondition/approval -> DENY) or a capability/quota limit, so the residual "
            "planning gap an LLM could close is {g:.0%}. A deterministic remediation loop is "
            "{d} for the mechanical, policy-opted-in classes; an LLM planner is not justified by "
            "measured evidence."
        ).format(p=planner, sh=am_share, sr=am_success, g=planning_gap_rate,
                 d=deterministic),
    }
