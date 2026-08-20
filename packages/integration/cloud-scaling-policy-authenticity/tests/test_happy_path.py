"""Positive controls: what the boundary must ADMIT, and exactly what admission means.

A suite of refusals proves nothing on its own — a verifier that refuses everything would
pass all of them. These are the properties that make the refusals meaningful.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    POLICY_AUTHORITY_PROTOCOL_ID,
    POLICY_TRUST_ANCHOR_OWNER,
    VERIFICATION_PROFILE,
    PolicyAuthenticityOutcome,
    require_verified_policy_authenticity,
)


@pytest.mark.happy
def test_a_genuinely_issued_policy_verifies_at_an_instant_inside_its_window():
    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is PolicyAuthenticityOutcome.VERIFIED
    assert result.verified is True
    assert result.refusal is None


@pytest.mark.happy
def test_the_verified_artifact_carries_the_complete_six_component_coordinate():
    authority, record = issued()
    verified = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    # All six, not three of six: this is the fact D-5B0B-3 measured Phase 5A cannot carry.
    assert verified.policy_family == record.coordinate.policy_family
    assert verified.policy_id == record.coordinate.policy_id
    assert verified.policy_version == record.coordinate.version
    assert verified.policy_content_digest == record.coordinate.content_digest
    assert verified.policy_scope == record.coordinate.scope
    assert verified.policy_tenant_id == record.coordinate.tenant_id
    assert verified.policy_coordinate == record.coordinate


@pytest.mark.happy
def test_the_verified_artifact_binds_the_body_digest_not_merely_the_content_digest():
    authority, record = issued()
    verified = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    assert verified.policy_body_digest == record.policy_body_digest
    # On a genuinely issued record the two are equal by a core issuance rule. The point of
    # D-5B0B-2 is which one is load-bearing when they are not — see test_coordinate_gap.py.
    assert verified.policy_content_digest == record.policy_body_digest


@pytest.mark.happy
def test_the_verified_artifact_names_who_issued_it_and_under_which_trust():
    authority, record = issued()
    verifier = verifier_for(authority)
    verified = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    assert verified.issuing_authority_id == record.issuing_authority_id
    assert verified.key_id == record.key_id
    assert verified.signature_alg == record.signature_alg
    assert verified.record_id == record.record_id
    assert verified.trust_configuration_digest == verifier.trust_configuration_digest
    assert verified.policy_trust_anchor_owner == POLICY_TRUST_ANCHOR_OWNER
    assert verified.authority_protocol_id == POLICY_AUTHORITY_PROTOCOL_ID
    assert verified.verification_profile == VERIFICATION_PROFILE


@pytest.mark.happy
def test_the_verified_artifact_carries_the_injected_instant_and_no_other():
    authority, record = issued()
    verified = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    assert verified.resolved_as_of_fact == T_MID
    assert verified.policy_issued_at_fact == record.issued_at


@pytest.mark.happy
def test_a_successful_result_carries_the_authority_s_own_resolution_and_the_policy_body():
    authority, record = issued()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    # The body reaches a consumer through the authority's type; the artifact binds it by
    # digest. Both halves matter: a digest alone cannot be read, and a body alone is unbound.
    assert result.resolution is not None
    assert result.resolution.policy is record.policy
    assert result.resolution.record is record


@pytest.mark.happy
def test_verification_is_deterministic_across_repeated_calls():
    authority, record = issued()
    verifier = verifier_for(authority)
    first = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy
    second = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy
    assert first.artifact_digest == second.artifact_digest
    assert first == second


@pytest.mark.happy
def test_a_genuine_artifact_revalidates_at_a_consumption_boundary():
    authority, record = issued()
    verified = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy
    assert require_verified_policy_authenticity(verified) is verified


@pytest.mark.happy
def test_a_tenant_scoped_policy_verifies_for_its_own_tenant():
    from _policy_fixtures import PolicyScope, make_authority, make_policy

    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    record = authority.issue(policy)
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id="tenant-a",
        as_of=T_MID,
    )
    assert result.outcome is PolicyAuthenticityOutcome.VERIFIED
    assert result.verified_policy.policy_tenant_id == "tenant-a"
    assert result.verified_policy.expected_reference_tenant_id == "tenant-a"
