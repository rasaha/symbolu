"""Observed-outcome labels and normalization (Phases 5-6).

Prediction and observation are independent; this module only turns a raw execution
result into a normalized observation label, applying the ground-truth precedence rule
(critical policy/compliance overrides operational success).
"""
from __future__ import annotations

from enum import Enum


class ObservedOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    QUOTA_FAILURE = "QUOTA_FAILURE"
    BILLING_FAILURE = "BILLING_FAILURE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    FEATURE_MISMATCH = "FEATURE_MISMATCH"
    CONTEXT_FAILURE = "CONTEXT_FAILURE"
    POLICY_PROHIBITED = "POLICY_PROHIBITED"
    RESIDENCY_PROHIBITED = "RESIDENCY_PROHIBITED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    UNKNOWN = "UNKNOWN"


# outcomes that represent a critical policy/compliance breach (override operational success)
CRITICAL_OUTCOMES = {ObservedOutcome.POLICY_PROHIBITED, ObservedOutcome.RESIDENCY_PROHIBITED}
# outcomes that mean the candidate was operationally executable (a real call returned valid text)
EXECUTABLE_OUTCOMES = {ObservedOutcome.SUCCESS}


def normalize(raw: dict) -> ObservedOutcome:
    """raw = {'attempted':bool, 'http':int|None, 'text_valid':bool, 'policy_permitted':bool,
             'timeout':bool, 'error_kind':str|None}. Precedence: critical policy overrides success."""
    if not raw.get("attempted", False):
        return ObservedOutcome.NOT_ATTEMPTED
    # critical policy/compliance evidence overrides operational success
    if raw.get("policy_permitted") is False:
        return ObservedOutcome(raw.get("critical_kind", "POLICY_PROHIBITED"))
    if raw.get("timeout"):
        return ObservedOutcome.TIMEOUT
    ek = raw.get("error_kind")
    if ek:
        try:
            return ObservedOutcome(ek)
        except ValueError:
            return ObservedOutcome.PROVIDER_ERROR
    if raw.get("http") in (401, 403):
        return ObservedOutcome.AUTH_FAILURE
    if raw.get("http") == 429:
        return ObservedOutcome.QUOTA_FAILURE
    if raw.get("http") == 404:
        return ObservedOutcome.MODEL_UNAVAILABLE
    if raw.get("text_valid") is False:
        return ObservedOutcome.INVALID_RESPONSE
    if raw.get("text_valid") is True and raw.get("http", 200) == 200:
        return ObservedOutcome.SUCCESS
    return ObservedOutcome.UNKNOWN


def is_false_eligible(predicted_selectable: bool, outcome: ObservedOutcome) -> bool:
    """A prediction of ELIGIBLE/CONDITIONAL that fails or breaches critical policy on attempt."""
    if not predicted_selectable:
        return False
    return outcome not in EXECUTABLE_OUTCOMES  # any non-success (incl critical) is false-eligible


def is_critical_false_eligible(predicted_selectable: bool, outcome: ObservedOutcome) -> bool:
    return predicted_selectable and outcome in CRITICAL_OUTCOMES
