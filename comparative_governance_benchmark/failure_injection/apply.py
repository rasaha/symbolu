"""Deterministic failure-profile application (Task 11).

Transforms a frozen scenario into a failure-injected one by setting the relevant
provider/execution fail flags (never touching the expected region). Registry
resolution failure cannot be expressed as scenario policy — it is signalled to the
strategy via a flag instead.
"""
from __future__ import annotations

import dataclasses

from enterprise_validation_pilot.schemas.scenario import HumanReviewSpec

from ..schemas.failure import FailureProfile


def needs_registry_failure(profile: FailureProfile) -> bool:
    return profile is FailureProfile.REGISTRY_RESOLUTION_FAILURE


def apply_profile(scenario, profile: FailureProfile):
    """Return a (possibly transformed) scenario for the given failure profile."""
    p = profile
    R = dataclasses.replace
    if p is FailureProfile.NORMAL or p is FailureProfile.REGISTRY_RESOLUTION_FAILURE:
        return scenario
    if p is FailureProfile.TAP_TIMEOUT:
        return R(scenario, tap_policy=R(scenario.tap_policy, fail="timeout"))
    if p is FailureProfile.TAP_UNAVAILABLE:
        return R(scenario, tap_policy=R(scenario.tap_policy, fail="unavailable"))
    if p is FailureProfile.TAP_MALFORMED_RESULT:
        return R(scenario, tap_policy=R(scenario.tap_policy, fail="malformed"))
    if p is FailureProfile.ACTIONGATE_TIMEOUT:
        return R(scenario, action_policy=R(scenario.action_policy, fail="timeout"))
    if p is FailureProfile.ACTIONGATE_UNAVAILABLE:
        return R(scenario, action_policy=R(scenario.action_policy, fail="unavailable"))
    if p is FailureProfile.ACTIONGATE_MALFORMED_RESULT:
        return R(scenario, action_policy=R(scenario.action_policy, fail="malformed"))
    if p is FailureProfile.EXECUTION_TIMEOUT:
        return R(scenario, execution=R(scenario.execution, timeout=True))
    if p is FailureProfile.EXECUTION_UNAVAILABLE:
        return R(scenario, execution=R(scenario.execution, transport_fail=True))
    if p is FailureProfile.EXECUTION_BUSINESS_REJECTION:
        return R(scenario, execution=R(scenario.execution, business_outcome="REJECTED"))
    if p is FailureProfile.RECONCILIATION_MISMATCH:
        return R(scenario, execution=R(scenario.execution,
                                       observed_overrides={"amount": "1"}))
    if p is FailureProfile.MISSING_OBLIGATION_EVIDENCE:
        return R(scenario, human_review=HumanReviewSpec(action="decline_action",
                                                        approver="senior",
                                                        note="obligation evidence withheld"))
    return scenario
