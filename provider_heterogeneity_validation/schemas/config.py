"""The six comparative configurations (Task 15) + resolution-policy wiring."""
from __future__ import annotations

from dataclasses import dataclass

from ..selection.resolve import ResolutionPolicy


@dataclass(frozen=True)
class Configuration:
    config_id: str
    description: str
    assertion_providers: tuple          # catalog membership (ids)
    action_providers: tuple
    assertion_policy: ResolutionPolicy
    action_policy: ResolutionPolicy
    assertion_preference: tuple = ()
    action_preference: tuple = ()
    assertion_fixed: str = ""
    action_fixed: str = ""
    allow_fallback: bool = False
    allow_degraded: bool = False
    capability_driven: bool = False


_TAP = "tap-primary"
_BA = "baseline-assertion"
_AG = "actiongate-primary"
_BAC = "baseline-action"

CONFIGURATIONS = {
    "C1": Configuration(
        "C1", "TAP + ActionGate (fixed)", (_TAP,), (_AG,),
        ResolutionPolicy.FIXED, ResolutionPolicy.FIXED,
        assertion_fixed=_TAP, action_fixed=_AG),
    "C2": Configuration(
        "C2", "TAP + Baseline Action (fixed)", (_TAP,), (_BAC,),
        ResolutionPolicy.FIXED, ResolutionPolicy.FIXED,
        assertion_fixed=_TAP, action_fixed=_BAC),
    "C3": Configuration(
        "C3", "Baseline Assertion + ActionGate (fixed)", (_BA,), (_AG,),
        ResolutionPolicy.FIXED, ResolutionPolicy.FIXED,
        assertion_fixed=_BA, action_fixed=_AG),
    "C4": Configuration(
        "C4", "Baseline Assertion + Baseline Action (fixed)", (_BA,), (_BAC,),
        ResolutionPolicy.FIXED, ResolutionPolicy.FIXED,
        assertion_fixed=_BA, action_fixed=_BAC),
    "C5": Configuration(
        "C5", "Preferred TAP/ActionGate with bounded fallback",
        (_TAP, _BA), (_AG, _BAC),
        ResolutionPolicy.BOUNDED_FALLBACK, ResolutionPolicy.BOUNDED_FALLBACK,
        assertion_preference=(_TAP, _BA), action_preference=(_AG, _BAC),
        allow_fallback=True, allow_degraded=True),
    "C6": Configuration(
        "C6", "Capability-driven selection", (_TAP, _BA), (_AG, _BAC),
        ResolutionPolicy.CAPABILITY_REQUIRED, ResolutionPolicy.CAPABILITY_REQUIRED,
        assertion_preference=(_BA, _TAP), action_preference=(_BAC, _AG),
        capability_driven=True),
}

CONFIG_ORDER = ("C1", "C2", "C3", "C4", "C5", "C6")
