"""Deterministic per-provider failure profiles (Task 12).

Each profile targets one provider (or a structural condition) and expresses its
effect as an engine failure mode and/or a selection-time state change, so the
runner exercises both provider-result indeterminacy (engine fails but the provider
is reachable/selected) and selection-time rejection (health/compat/capability).
"""
from __future__ import annotations

from enum import Enum


class FailureProfile(str, Enum):
    NORMAL = "NORMAL"
    TAP_TIMEOUT = "TAP_TIMEOUT"
    TAP_UNAVAILABLE = "TAP_UNAVAILABLE"
    TAP_MALFORMED_RESULT = "TAP_MALFORMED_RESULT"
    TAP_INCOMPATIBLE = "TAP_INCOMPATIBLE"
    TAP_DEGRADED = "TAP_DEGRADED"
    BASELINE_ASSERTION_TIMEOUT = "BASELINE_ASSERTION_TIMEOUT"
    BASELINE_ASSERTION_UNAVAILABLE = "BASELINE_ASSERTION_UNAVAILABLE"
    BASELINE_ASSERTION_MALFORMED_RESULT = "BASELINE_ASSERTION_MALFORMED_RESULT"
    BASELINE_ASSERTION_INCOMPATIBLE = "BASELINE_ASSERTION_INCOMPATIBLE"
    ACTIONGATE_TIMEOUT = "ACTIONGATE_TIMEOUT"
    ACTIONGATE_UNAVAILABLE = "ACTIONGATE_UNAVAILABLE"
    ACTIONGATE_MALFORMED_RESULT = "ACTIONGATE_MALFORMED_RESULT"
    ACTIONGATE_INCOMPATIBLE = "ACTIONGATE_INCOMPATIBLE"
    ACTIONGATE_DEGRADED = "ACTIONGATE_DEGRADED"
    BASELINE_ACTION_TIMEOUT = "BASELINE_ACTION_TIMEOUT"
    BASELINE_ACTION_UNAVAILABLE = "BASELINE_ACTION_UNAVAILABLE"
    BASELINE_ACTION_MALFORMED_RESULT = "BASELINE_ACTION_MALFORMED_RESULT"
    BASELINE_ACTION_INCOMPATIBLE = "BASELINE_ACTION_INCOMPATIBLE"
    REGISTRY_DUPLICATE_ID = "REGISTRY_DUPLICATE_ID"
    NO_COMPATIBLE_PROVIDER = "NO_COMPATIBLE_PROVIDER"
    NO_CAPABILITY_MATCH = "NO_CAPABILITY_MATCH"


_TARGET = {
    "TAP": "tap-primary", "BASELINE_ASSERTION": "baseline-assertion",
    "ACTIONGATE": "actiongate-primary", "BASELINE_ACTION": "baseline-action",
}


def _prefix(name: str) -> str:
    for p in ("BASELINE_ASSERTION", "BASELINE_ACTION", "ACTIONGATE", "TAP"):
        if name.startswith(p):
            return p
    return ""


def failure_effect(profile: FailureProfile) -> dict:
    """Return {target, engine_fail, state, special} describing the injection."""
    name = profile.value
    if profile is FailureProfile.NORMAL:
        return {"target": None, "engine_fail": None, "state": None, "special": None}
    if name in ("REGISTRY_DUPLICATE_ID", "NO_COMPATIBLE_PROVIDER", "NO_CAPABILITY_MATCH"):
        return {"target": None, "engine_fail": None, "state": None, "special": name}
    target = _TARGET[_prefix(name)]
    if name.endswith("TIMEOUT"):
        return {"target": target, "engine_fail": "timeout", "state": None, "special": None}
    if name.endswith("MALFORMED_RESULT"):
        return {"target": target, "engine_fail": "malformed", "state": None, "special": None}
    if name.endswith("UNAVAILABLE"):
        return {"target": target, "engine_fail": "unavailable",
                "state": {"health": "UNAVAILABLE"}, "special": None}
    if name.endswith("INCOMPATIBLE"):
        return {"target": target, "engine_fail": None,
                "state": {"compatible": False}, "special": None}
    if name.endswith("DEGRADED"):
        return {"target": target, "engine_fail": None,
                "state": {"health": "DEGRADED"}, "special": None}
    return {"target": None, "engine_fail": None, "state": None, "special": None}


REQUIRED_PROFILES = tuple(FailureProfile)


def kind_of(profile: FailureProfile) -> str:
    p = _prefix(profile.value)
    if p in ("TAP", "BASELINE_ASSERTION"):
        return "ASSERTION_GOVERNANCE"
    if p in ("ACTIONGATE", "BASELINE_ACTION"):
        return "ACTION_GOVERNANCE"
    return ""
