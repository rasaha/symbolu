"""Deterministic failure profiles + applicability (Task 11).

A failure profile is applied only to strategies that contain the relevant
component. Non-applicability is never scored as success.
"""
from __future__ import annotations

from enum import Enum


class FailureProfile(str, Enum):
    NORMAL = "NORMAL"
    TAP_TIMEOUT = "TAP_TIMEOUT"
    TAP_UNAVAILABLE = "TAP_UNAVAILABLE"
    TAP_MALFORMED_RESULT = "TAP_MALFORMED_RESULT"
    ACTIONGATE_TIMEOUT = "ACTIONGATE_TIMEOUT"
    ACTIONGATE_UNAVAILABLE = "ACTIONGATE_UNAVAILABLE"
    ACTIONGATE_MALFORMED_RESULT = "ACTIONGATE_MALFORMED_RESULT"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    EXECUTION_UNAVAILABLE = "EXECUTION_UNAVAILABLE"
    EXECUTION_BUSINESS_REJECTION = "EXECUTION_BUSINESS_REJECTION"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    MISSING_OBLIGATION_EVIDENCE = "MISSING_OBLIGATION_EVIDENCE"
    REGISTRY_RESOLUTION_FAILURE = "REGISTRY_RESOLUTION_FAILURE"


_TAP = {"TAP_TIMEOUT", "TAP_UNAVAILABLE", "TAP_MALFORMED_RESULT"}
# reconciliation-mismatch and obligation-evidence detection require the action-
# governance lifecycle, so they are scoped to the ActionGate component.
_ACTIONGATE = {"ACTIONGATE_TIMEOUT", "ACTIONGATE_UNAVAILABLE", "ACTIONGATE_MALFORMED_RESULT",
               "REGISTRY_RESOLUTION_FAILURE", "RECONCILIATION_MISMATCH",
               "MISSING_OBLIGATION_EVIDENCE"}
_EXECUTION = {"EXECUTION_TIMEOUT", "EXECUTION_UNAVAILABLE", "EXECUTION_BUSINESS_REJECTION"}

#: which governance components each strategy contains
STRATEGY_COMPONENTS = {
    "no_governance": frozenset({"execution"}),
    "action_only": frozenset({"actiongate", "execution"}),
    "assertion_only": frozenset({"tap", "execution"}),
    "full_governance": frozenset({"tap", "actiongate", "execution"}),
}


def applies_to(profile: FailureProfile, strategy_id: str) -> bool:
    """A failure profile applies to a strategy only if the strategy has the component."""
    if profile is FailureProfile.NORMAL:
        return True
    comps = STRATEGY_COMPONENTS[strategy_id]
    p = profile.value
    if p in _TAP:
        return "tap" in comps
    if p in _ACTIONGATE:
        return "actiongate" in comps
    if p in _EXECUTION:
        return "execution" in comps
    return False


REQUIRED_PROFILES = tuple(FailureProfile)
