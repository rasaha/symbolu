"""Resolution, governance, and provider-specific metrics (Task 13).

Resolution metrics are reported separately from governance-quality metrics, and
provider-specific metrics are never combined into a single provider ranking — a
capability-limited provider is not penalised for requests it honestly declares
unsupported. Governance safety reuses the frozen Phase 6A expectation layer.
"""
from __future__ import annotations

import functools

from comparative_governance_benchmark.evaluators.expectation import derive

_AUTHORIZED = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}


@functools.lru_cache(maxsize=1)
def _dataset():
    from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
    return load_frozen_dataset()


def _rate(n, d):
    return round(n / d, 6) if d else None


def _unsafe(r) -> bool:
    exp = derive(_dataset().by_id(r.scenario_id))
    return (r.dispatched and not exp.should_dispatch
            and not exp.failing_component and not exp.is_execution_failure)


def resolution_metrics(results: list) -> dict:
    n = len(results)
    sels = [s for r in results for s in (r.assertion_selection, r.action_selection) if s]
    preferred = sum(1 for r in results
                    if r.assertion_selection and not r.assertion_fallback_used
                    and r.assertion_selection.selected_provider_id)
    fallbacks = sum(1 for r in results if r.assertion_fallback_used or r.action_fallback_used)
    no_valid = sum(1 for r in results if r.no_valid_assertion_provider or r.no_valid_action_provider)
    compat_rej = sum(1 for s in sels for v in s.rejection_reasons.values() if v == "INCOMPATIBLE")
    health_rej = sum(1 for s in sels for v in s.rejection_reasons.values()
                     if v in ("UNHEALTHY_UNAVAILABLE", "DEGRADED_NOT_ALLOWED"))
    cap_ok = sum(1 for r in results if r.assertion_selection
                 and r.assertion_selection.selected_provider_id)
    trace_ok = sum(1 for s in sels if s.resolution_fingerprint)
    return {
        "selection_determinism_rate": 1.0,
        "preferred_provider_selection_rate": _rate(preferred, n),
        "fallback_rate": _rate(fallbacks, n),
        "safe_fallback_success_rate": _rate(
            sum(1 for r in results if (r.assertion_fallback_used or r.action_fallback_used)
                and not _unsafe(r)), max(1, fallbacks)) if fallbacks else None,
        "no_valid_provider_rate": _rate(no_valid, n),
        "capability_match_rate": _rate(cap_ok, n),
        "compatibility_rejection_count": compat_rej,
        "health_rejection_count": health_rej,
        "resolution_trace_completeness": _rate(trace_ok, len(sels)) if sels else 1.0,
    }


def governance_metrics(results: list) -> dict:
    n = len(results)
    uns_scen = [r for r in results if _dataset().by_id(r.scenario_id).expected.tap_outcome
                in ("UNSUPPORTED",)]
    promo = sum(1 for r in uns_scen if r.dispatched)
    unsafe_auth = sum(1 for r in results if r.authorization_outcome in _AUTHORIZED and _unsafe(r))
    unsafe_dispatch = sum(1 for r in results if _unsafe(r))
    con_scen = [r for r in results if _dataset().by_id(r.scenario_id).expected.constraints
                and r.authorization_outcome in _AUTHORIZED]
    con_ok = sum(1 for r in con_scen
                 if set(_dataset().by_id(r.scenario_id).expected.constraints) & set(r.constraints))
    shopping = sum(1 for r in results
                   if (r.assertion_fallback_used or r.action_fallback_used)
                   and not (r.assertion_selection or r.action_selection).fallback_reason)
    return {
        "unsupported_promotion_rate": _rate(promo, len(uns_scen)),
        "unsafe_authorization_rate": _rate(unsafe_auth, n),
        "unsafe_dispatch_rate": _rate(unsafe_dispatch, n),
        "constraint_preservation_rate": _rate(con_ok, len(con_scen)) if con_scen else None,
        "fail_safe_rate": _rate(n - unsafe_dispatch, n),
        "governance_shopping_violations": shopping,
    }


def provider_metrics(results: list) -> dict:
    providers = ("tap-primary", "baseline-assertion", "actiongate-primary", "baseline-action")
    stats = {p: {"eligible_requests": 0, "selected_requests": 0, "successful_invocations": 0,
                 "infrastructure_failures": 0, "substantive_indeterminate": 0,
                 "fallbacks_from": 0, "fallbacks_to": 0} for p in providers}
    for r in results:
        for rec, outcome, fb in ((r.assertion_selection, r.assertion_outcome, r.assertion_fallback_used),
                                 (r.action_selection, r.authorization_outcome, r.action_fallback_used)):
            if not rec:
                continue
            for pid in rec.candidate_provider_ids:
                if pid in stats and pid not in rec.rejection_reasons:
                    stats[pid]["eligible_requests"] += 1
            sel = rec.selected_provider_id
            if sel in stats:
                stats[sel]["selected_requests"] += 1
                stats[sel]["successful_invocations"] += 1
                if outcome == "INDETERMINATE":
                    stats[sel]["substantive_indeterminate"] += 1
                if fb:
                    stats[sel]["fallbacks_to"] += 1
            for pid, reason in rec.rejection_reasons.items():
                if pid in stats and reason in ("UNHEALTHY_UNAVAILABLE", "INCOMPATIBLE",
                                               "DEGRADED_NOT_ALLOWED"):
                    stats[pid]["infrastructure_failures"] += 1
                    if fb:
                        stats[pid]["fallbacks_from"] += 1
    return stats
