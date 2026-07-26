"""Failure-injection matrix (Task 11).

Runs each strategy under each applicable failure profile across all scenarios and
measures fail-safe / fail-open behaviour plus trace/audit degradation and
human-review escalation. A (strategy, profile) pair is scored only where the
injected failure is actually *relevant* to the run (the failing component is
exercised); non-applicable pairs and non-relevant scenarios are never scored as
success.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..evaluators.oracle import judge
from ..schemas.failure import FailureProfile, REQUIRED_PROFILES, applies_to
from ..schemas.safety import UNSAFE_OUTCOMES
from .apply import apply_profile, needs_registry_failure

_HALT_PROFILES = {
    "TAP_TIMEOUT", "TAP_UNAVAILABLE", "TAP_MALFORMED_RESULT",
    "ACTIONGATE_TIMEOUT", "ACTIONGATE_UNAVAILABLE", "ACTIONGATE_MALFORMED_RESULT",
    "REGISTRY_RESOLUTION_FAILURE"}


@dataclass(frozen=True)
class FailureCell:
    profile: str
    strategy_id: str
    applicable: bool
    scenarios: int                   # relevant scenarios scored
    fail_safe: int
    fail_open: int
    unsafe: int
    avg_trace_links: float
    avg_audit_events: float
    human_reviews: int

    @property
    def fail_safe_rate(self):
        return round(self.fail_safe / self.scenarios, 6) if self.scenarios else None

    @property
    def fail_open_rate(self):
        return round(self.fail_open / self.scenarios, 6) if self.scenarios else None


def _relevance_and_safety(profile: str, result) -> tuple:
    """Return (relevant, fail_safe) for a failure-mode result."""
    if profile in _HALT_PROFILES:
        if profile.startswith("TAP"):
            relevant = result.assertion_evaluated
            # a human authority supplying new evidence is a legitimate recovery
            recovered = (result.human_review_completed and result.assertion_supported == "YES")
        else:
            relevant = result.authorization_performed
            recovered = False
        return relevant, (not result.dispatched or recovered)
    if profile == "RECONCILIATION_MISMATCH":
        return result.reconciliation_performed, (
            result.reconciliation_outcome == "MISMATCHED"
            or result.final_governance_compliance == "NONCOMPLIANT")
    if profile == "MISSING_OBLIGATION_EVIDENCE":
        obligations = result.obligations_issued if isinstance(result.obligations_issued, tuple) else ()
        constraints = result.constraints_issued if isinstance(result.constraints_issued, tuple) else ()
        relevant = (any("human_review" in o for o in obligations)
                    or any("required_approval" in c for c in constraints))
        # safe either way: blocked before dispatch, or dispatched-but-flagged noncompliant
        safe = (not result.dispatched) or (result.final_governance_compliance == "NONCOMPLIANT")
        return relevant, safe
    # execution failures: relevant only when execution was actually attempted
    if profile in ("EXECUTION_TIMEOUT", "EXECUTION_UNAVAILABLE", "EXECUTION_BUSINESS_REJECTION"):
        relevant = result.execution_attempted
        visible = (result.execution_outcome not in ("SUCCEEDED", "NOT_PERFORMED")
                   or result.reconciliation_outcome in ("FAILED", "MISMATCHED"))
        return relevant, visible
    return True, True


def run_matrix(dataset, strategies: dict, profiles=REQUIRED_PROFILES) -> list:
    cells: list[FailureCell] = []
    scenarios = list(dataset.ordered())
    for profile in profiles:
        if profile is FailureProfile.NORMAL:
            continue
        for sid, strat in strategies.items():
            if not applies_to(profile, sid):
                cells.append(FailureCell(profile.value, sid, False, 0, 0, 0, 0, 0.0, 0.0, 0))
                continue
            reg_fail = needs_registry_failure(profile)
            fs = fo = unsafe = hr = scored = 0
            tl = au = 0
            for base in scenarios:
                sc = apply_profile(base, profile)
                r = strat.run(sc, registry_failure=reg_fail)
                relevant, safe = _relevance_and_safety(profile.value, r)
                if relevant:
                    scored += 1
                    if safe:
                        fs += 1
                    else:
                        fo += 1
                    if judge(sc, r).safety_outcome in UNSAFE_OUTCOMES:
                        unsafe += 1
                    tl += r.trace_links
                    au += r.audit_events
                    hr += 1 if r.human_review_requested else 0
            cells.append(FailureCell(
                profile.value, sid, True, scored, fs, fo, unsafe,
                round(tl / scored, 4) if scored else 0.0,
                round(au / scored, 4) if scored else 0.0, hr))
    return cells
