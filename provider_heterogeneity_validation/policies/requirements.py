"""Capability requirements derived from frozen scenario semantics (Task 14).

Derives the mandatory capabilities a scenario needs from its declared policy —
never from provider output. Used by capability-driven selection (C6) and by the
cost/benefit frontier. Requiring only capabilities the *baseline* providers lack
means capability-driven routing prefers the lighter provider when it is sufficient
and escalates to TAP/ActionGate only when genuinely required.
"""
from __future__ import annotations

# capability the baseline assertion provider lacks (needs TAP)
_ASSERTION_RICH = "qualifier_detection"

# action constraint type -> capability the baseline action provider lacks (needs ActionGate)
_ACTION_CAP_BY_CONSTRAINT = {
    "required_approval": "required_approval",
    "single_use": "single_use",
    "allowed_region": "region_limits",
    "execution_deadline": "expiry",
    "allowed_resource": "resource_scope_limits",
    "parameter_restriction": "parameter_restrictions",
    "rate_limit": "rate_limits",
}


def required_assertion_capabilities(scenario) -> tuple:
    # an assertion TAP resolves as CONSTRAINED requires rich qualifier/component
    # analysis the baseline cannot perform.
    if scenario.tap_policy.outcome == "CONSTRAINED":
        return (_ASSERTION_RICH,)
    return ()


def required_action_capabilities(scenario) -> tuple:
    caps = []
    for ctype, _v in scenario.action_policy.constraints:
        cap = _ACTION_CAP_BY_CONSTRAINT.get(ctype)
        if cap:
            caps.append(cap)
    return tuple(sorted(set(caps)))
