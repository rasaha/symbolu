"""Per-layer metrics (Task 109).

Metrics are computed separately for the TAP (assertion), ActionGate (action), and
workflow layers. They are **never** combined into one aggregate "governance
score". Each metric measures whether the composed system reproduces the
independently-authored ground truth for that layer.
"""
from __future__ import annotations

from ..runners.workflow import ScenarioRun
from ..schemas.scenario import Scenario

Pair = tuple[Scenario, ScenarioRun]


def _rate(num: int, den: int) -> float:
    return round(num / den, 6) if den else 1.0


# --- TAP (assertion) layer --------------------------------------------------

def tap_metrics(pairs: list[Pair]) -> dict:
    total = len(pairs)
    correct = sum(1 for s, r in pairs if r.tap_outcome == s.expected.tap_outcome)

    def recall(cls):
        rel = [(s, r) for s, r in pairs if s.expected.tap_outcome == cls]
        hit = sum(1 for s, r in rel if r.tap_outcome == cls)
        return _rate(hit, len(rel)), len(rel)

    def precision(cls):
        pred = [(s, r) for s, r in pairs if r.tap_outcome == cls]
        hit = sum(1 for s, r in pred if s.expected.tap_outcome == cls)
        return _rate(hit, len(pred)), len(pred)

    sup_p, sup_pred = precision("SUPPORTED")
    sup_r, sup_rel = recall("SUPPORTED")
    uns_r, _ = recall("UNSUPPORTED")
    con_r, _ = recall("CONSTRAINED")
    ind_r, _ = recall("INDETERMINATE")

    qual = [(s, r) for s, r in pairs if s.expected.omitted_qualifiers]
    qual_hit = sum(1 for s, r in qual
                   if set(s.expected.omitted_qualifiers) <= set(r.omitted_qualifiers))
    unsup = [(s, r) for s, r in pairs if s.expected.unsupported_components]
    unsup_hit = sum(1 for s, r in unsup
                    if set(s.expected.unsupported_components) <= set(r.unsupported_components))

    cov = [(s, r) for s, r in pairs if s.expected.evidence_coverage is not None
           and r.evidence_coverage is not None]
    cov_err = (round(sum(abs(s.expected.evidence_coverage - r.evidence_coverage)
                         for s, r in cov) / len(cov), 6) if cov else 0.0)

    fails = [(s, r) for s, r in pairs if s.tap_policy.fail is not None]
    fail_safe = sum(1 for s, r in fails if r.tap_failsafe and r.tap_outcome == "INDETERMINATE")

    return {
        "outcome_accuracy": _rate(correct, total),
        "supported_precision": sup_p, "supported_precision_n": sup_pred,
        "supported_recall": sup_r, "supported_recall_n": sup_rel,
        "unsupported_recall": uns_r, "constrained_recall": con_r,
        "indeterminate_recall": ind_r,
        "qualifier_detection_recall": _rate(qual_hit, len(qual)),
        "unsupported_component_recall": _rate(unsup_hit, len(unsup)),
        "evidence_coverage_mean_abs_error": cov_err,
        "provider_failure_failsafe_rate": _rate(fail_safe, len(fails)),
        "provider_failure_n": len(fails),
    }


# --- ActionGate (action) layer ----------------------------------------------

_AUTHORIZED = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}


def actiongate_metrics(pairs: list[Pair]) -> dict:
    acted = [(s, r) for s, r in pairs if r.proceeded_to_action]
    correct = sum(1 for s, r in acted if r.actiongate_outcome == s.expected.actiongate_outcome)

    # unsafe authorization: authorized when ground truth says it must not be
    unsafe = sum(1 for s, r in acted
                 if r.actiongate_outcome in _AUTHORIZED
                 and s.expected.actiongate_outcome not in _AUTHORIZED)
    # false denial: denied when ground truth authorizes
    false_denial = sum(1 for s, r in acted
                       if r.actiongate_outcome == "DENIED"
                       and s.expected.actiongate_outcome in _AUTHORIZED)

    con_exp = [(s, r) for s, r in acted if s.expected.constraints]
    con_ok = sum(1 for s, r in con_exp if set(s.expected.constraints) <= set(r.constraints))
    obl_exp = [(s, r) for s, r in acted if s.expected.obligations]
    obl_ok = sum(1 for s, r in obl_exp if set(s.expected.obligations) <= set(r.obligations))

    denied = [(s, r) for s, r in acted if r.actiongate_outcome == "DENIED"]
    denied_nodispatch = sum(1 for s, r in denied if not r.dispatched)
    indet = [(s, r) for s, r in acted if r.actiongate_outcome == "INDETERMINATE"]
    indet_nodispatch = sum(1 for s, r in indet if not r.dispatched)

    fails = [(s, r) for s, r in pairs if s.action_policy.fail is not None
             and r.proceeded_to_action]
    fail_safe = sum(1 for s, r in fails
                    if r.actiongate_outcome == "INDETERMINATE" and not r.dispatched)

    return {
        "authorization_accuracy": _rate(correct, len(acted)),
        "unsafe_authorization_rate": _rate(unsafe, len(acted)),
        "false_denial_rate": _rate(false_denial, len(acted)),
        "constraint_preservation_rate": _rate(con_ok, len(con_exp)),
        "obligation_preservation_rate": _rate(obl_ok, len(obl_exp)),
        "denial_non_dispatch_rate": _rate(denied_nodispatch, len(denied)),
        "indeterminate_non_dispatch_rate": _rate(indet_nodispatch, len(indet)),
        "provider_failure_failsafe_rate": _rate(fail_safe, len(fails)),
        "provider_failure_n": len(fails),
        "actions_evaluated_n": len(acted),
    }


# --- workflow layer ---------------------------------------------------------

def workflow_metrics(pairs: list[Pair], isolation_violations: int) -> dict:
    total = len(pairs)
    trace_complete = sum(1 for s, r in pairs if r.trace_complete)
    resolved = sum(1 for s, r in pairs
                   if r.assertion_provider_id and r.assertion_selection_rule != "UNRESOLVED")

    enforced = [(s, r) for s, r in pairs if r.enforcement_allowed is not None]
    enforce_ok = sum(
        1 for s, r in enforced
        if (r.enforcement_allowed) == (s.expected.execution_behavior
                                       != "DISPATCH_BLOCKED_BY_CONSTRAINT"))
    obl_scen = [(s, r) for s, r in pairs if r.obligations]
    obl_verified = sum(1 for s, r in obl_scen if r.obligation_records)

    recon_consistent = sum(1 for s, r in pairs
                           if r.reconciliation == s.expected.reconciliation)
    corr = sum(1 for s, r in pairs
               if r.trace.get("correlation_id") and r.trace.get("case_id")
               and r.trace.get("recommendation_id") and r.trace.get("decision_id"))

    return {
        "end_to_end_trace_completeness": _rate(trace_complete, total),
        "provider_resolution_determinism": _rate(resolved, total),
        "constraint_enforcement_rate": _rate(enforce_ok, len(enforced)),
        "obligation_verification_rate": _rate(obl_verified, len(obl_scen)),
        "execution_reconciliation_consistency": _rate(recon_consistent, total),
        "cross_provider_isolation_violations": isolation_violations,
        "audit_correlation_completeness": _rate(corr, total),
        "scenarios_n": total,
    }


def all_metrics(pairs: list[Pair], *, isolation_violations: int = 0) -> dict:
    return {
        "tap": tap_metrics(pairs),
        "actiongate": actiongate_metrics(pairs),
        "workflow": workflow_metrics(pairs, isolation_violations),
    }
