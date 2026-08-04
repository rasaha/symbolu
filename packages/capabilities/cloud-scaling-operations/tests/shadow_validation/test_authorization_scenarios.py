"""Synthetic authorization scenarios: fail-closed, granular, reproducible, shadow-only."""
from __future__ import annotations

from shadow_validation.authorization_scenarios import (
    run_all_scenarios, AUTHORIZED_FOR_SHADOW_PLAN, FIXED_NOW,
)

_REQUIRED = {
    "valid_matching_authorization", "missing_authorization", "expired_authorization",
    "not_yet_valid_authorization", "malformed_authorization", "tenant_mismatch",
    "cluster_mismatch", "namespace_mismatch", "resource_kind_mismatch",
    "resource_name_mismatch", "action_mismatch", "replica_bounds_exceeded",
    "maximum_delta_exceeded", "recommendation_mismatch", "policy_version_mismatch",
    "stale_observation", "untrusted_issuer", "invalid_test_signature",
    "reused_nonce", "reused_authorization_changed_target",
}


def test_all_scenarios_present_and_correct():
    results = {r.scenario: r for r in run_all_scenarios()}
    assert _REQUIRED.issubset(set(results)), _REQUIRED - set(results)
    for r in results.values():
        assert r.ok, f"{r.scenario}: got {r.result}/{r.denial_code}, expected {r.expected_result}"


def test_only_valid_scenario_is_authorized_and_only_for_shadow():
    results = run_all_scenarios()
    authorized = [r for r in results if r.result == AUTHORIZED_FOR_SHADOW_PLAN]
    assert [r.scenario for r in authorized] == ["valid_matching_authorization"]
    # There is no live-execution result anywhere.
    assert all("LIVE" not in r.result for r in results)


def test_scenarios_are_deterministic():
    a = [r.to_dict() for r in run_all_scenarios(FIXED_NOW)]
    b = [r.to_dict() for r in run_all_scenarios(FIXED_NOW)]
    assert a == b


def test_each_denial_has_a_granular_code():
    for r in run_all_scenarios():
        if r.result != AUTHORIZED_FOR_SHADOW_PLAN:
            assert r.denial_code, r.scenario
