"""``PolicyTargetBindingReferenceV2`` — the coordinate the candidate carries (5B-1).

The residual this closes, stated as the failure it was: a Phase 5A binding carries three of a
Policy Authority coordinate's six components, and its fourth is in the wrong digest namespace,
so nothing in a candidate could name a policy version. A verified policy proof therefore
verified alongside *any* candidate, including one whose binding named a different policy.

What is measured here is only what Phase 5A can establish: that the coordinate is complete,
that it is bound to this exact scope, that its two digest namespaces stay separate, and that a
candidate cannot carry two policy references naming different policies. Nothing here resolves
anything — Phase 5A still verifies no signature, consults no registry and reads no clock, and
both references still report ``PRESENT_BUT_NOT_TRUST_VERIFIED``.
"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import (
    build_attestation,
    build_decision,
    build_policy_binding,
    build_policy_coordinate_binding,
    build_projection,
    build_target_scope,
    coordinate_for,
)
from ugence_cloud_scaling_authorization_contracts import (
    POLICY_COORDINATE_COMPONENTS,
    POLICY_TARGET_BINDING_V2_SCHEMA_VERSION,
    AuthorizationCandidateRejectionReason as Reason,
)
from ugence_cloud_scaling_authorization_contracts import (
    CanonicalFieldError,
    ExactTypeError,
    PolicyTargetBindingError,
    PolicyTargetBindingReference,
    PolicyTargetBindingReferenceV2,
    build_capacity_authorization_candidate,
    is_canonical_digest,
    is_policy_authority_digest,
)
from ugence_cloud_scaling_authorization_contracts.trust import PHASE_5A_TRUST_STATE

BARE = "b" * 64
PREFIXED = "sha256:" + "c" * 64


def _build(**overrides):
    """Build a candidate through the real builder, varying only what a test names."""

    projection = build_projection()
    decision = build_decision(projection)
    attestation = build_attestation(recommendation_digest=projection.recommendation_digest)
    scope = overrides.pop("target_scope", None) or build_target_scope(projection)
    binding = overrides.pop("policy_binding", None) or build_policy_binding(scope)
    coordinate = overrides.pop("policy_coordinate_binding", None) or coordinate_for(binding)
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=binding,
        policy_coordinate_binding=coordinate,
        target_scope=scope,
    )


# ======================================================================================
# The coordinate is complete — D-5B1-5
# ======================================================================================


def test_all_six_coordinate_components_are_required_fields():
    """No default, no ``Optional``: five of six is not a partially specified coordinate."""

    fields = {f.name: f for f in dataclasses.fields(PolicyTargetBindingReferenceV2)}
    assert set(POLICY_COORDINATE_COMPONENTS) <= set(fields)
    for name in POLICY_COORDINATE_COMPONENTS:
        assert fields[name].default is dataclasses.MISSING, name
        assert fields[name].default_factory is dataclasses.MISSING, name


def test_the_coordinate_accessor_returns_exactly_the_six_components(target_scope):
    coordinate = build_policy_coordinate_binding(target_scope)
    assert set(coordinate.policy_coordinate()) == set(POLICY_COORDINATE_COMPONENTS)
    assert len(POLICY_COORDINATE_COMPONENTS) == 6


@pytest.mark.parametrize("component", POLICY_COORDINATE_COMPONENTS)
def test_an_omitted_coordinate_component_cannot_be_deserialized(target_scope, component):
    """A dictionary missing any component is refused rather than defaulted."""

    data = build_policy_coordinate_binding(target_scope).to_canonical_dict()
    data.pop("trust_state")
    data.pop(component)
    with pytest.raises(CanonicalFieldError) as exc:
        PolicyTargetBindingReferenceV2.from_dict(data)
    assert exc.value.reason is Reason.MALFORMED_POLICY_COORDINATE_BINDING


def test_an_empty_tenant_component_is_admitted_but_a_missing_one_is_not(target_scope):
    """The authority's global tenant *is* the empty string; absence is still absence."""

    globally_scoped = build_policy_coordinate_binding(
        target_scope, policy_scope="GLOBAL", policy_tenant_id=""
    )
    assert globally_scoped.policy_tenant_id == ""

    data = globally_scoped.to_canonical_dict()
    data.pop("trust_state")
    data.pop("policy_tenant_id")
    with pytest.raises(CanonicalFieldError):
        PolicyTargetBindingReferenceV2.from_dict(data)


# ======================================================================================
# Two digest namespaces, never converted — D-5B1-4
# ======================================================================================


def test_the_policy_digests_are_bare_and_the_phase5a_digests_are_prefixed(target_scope):
    coordinate = build_policy_coordinate_binding(target_scope)
    for value in (coordinate.policy_content_digest, coordinate.policy_body_digest):
        assert is_policy_authority_digest(value) and not is_canonical_digest(value)
    for value in (coordinate.target_scope_digest, coordinate.binding_digest):
        assert is_canonical_digest(value) and not is_policy_authority_digest(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_content_digest", PREFIXED),
        ("policy_body_digest", PREFIXED),
        ("policy_content_digest", "B" * 64),
        ("policy_body_digest", "not-a-digest"),
    ],
)
def test_a_reprefixed_policy_digest_is_refused(target_scope, field, value):
    """A ``sha256:``-prefixed policy digest is a digest nobody signed. It is not adapted."""

    good = build_policy_coordinate_binding(target_scope)
    with pytest.raises(CanonicalFieldError) as exc:
        dataclasses.replace(good, **{field: value})
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD


@pytest.mark.parametrize("field", ["target_scope_digest", "binding_digest"])
def test_a_bare_phase5a_digest_is_refused(target_scope, field):
    good = build_policy_coordinate_binding(target_scope)
    with pytest.raises(CanonicalFieldError):
        dataclasses.replace(good, **{field: BARE})


def test_the_content_and_body_digests_must_be_the_same_value(target_scope):
    """The R-3 equality, refused here because the authority does not re-enforce it."""

    good = build_policy_coordinate_binding(target_scope)
    with pytest.raises(PolicyTargetBindingError) as exc:
        dataclasses.replace(good, policy_content_digest="a" * 64)
    assert exc.value.reason is Reason.MALFORMED_POLICY_COORDINATE_BINDING


# ======================================================================================
# Self-consistency and strict deserialization
# ======================================================================================


def test_the_binding_digest_is_self_validating(target_scope):
    good = build_policy_coordinate_binding(target_scope)
    with pytest.raises(PolicyTargetBindingError) as exc:
        dataclasses.replace(good, binding_digest="sha256:" + "d" * 64)
    assert exc.value.reason is Reason.MALFORMED_POLICY_COORDINATE_BINDING


def test_a_mutated_component_no_longer_matches_its_own_digest(target_scope):
    good = build_policy_coordinate_binding(target_scope)
    with pytest.raises(PolicyTargetBindingError):
        dataclasses.replace(good, policy_family="something-else")


def test_the_round_trip_through_from_dict_is_exact(target_scope):
    good = build_policy_coordinate_binding(target_scope)
    data = good.to_canonical_dict()
    data.pop("trust_state")
    assert PolicyTargetBindingReferenceV2.from_dict(data) == good


def test_a_forged_trust_state_is_named_as_such(target_scope):
    data = build_policy_coordinate_binding(target_scope).to_canonical_dict()
    with pytest.raises(CanonicalFieldError) as exc:
        PolicyTargetBindingReferenceV2.from_dict(data)
    assert exc.value.reason is Reason.FORGED_TRUST_STATE


def test_an_unknown_field_is_refused(target_scope):
    data = build_policy_coordinate_binding(target_scope).to_canonical_dict()
    data.pop("trust_state")
    data["issued_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises(CanonicalFieldError) as exc:
        PolicyTargetBindingReferenceV2.from_dict(data)
    assert exc.value.reason is Reason.UNKNOWN_FIELD


def test_a_field_claiming_the_coordinate_was_resolved_is_named_as_a_forgery(target_scope):
    """``resolved`` sits beside ``verified`` in the refusal set: neither is a Phase 5A word."""

    data = build_policy_coordinate_binding(target_scope).to_canonical_dict()
    data.pop("trust_state")
    data["resolved"] = True
    with pytest.raises(CanonicalFieldError) as exc:
        PolicyTargetBindingReferenceV2.from_dict(data)
    assert exc.value.reason is Reason.FORGED_TRUST_STATE


def test_the_trust_state_is_the_single_unverified_state_and_is_derived(target_scope):
    """Carrying a complete coordinate is not resolving it."""

    coordinate = build_policy_coordinate_binding(target_scope)
    assert coordinate.trust_state is PHASE_5A_TRUST_STATE
    with pytest.raises(dataclasses.FrozenInstanceError):
        coordinate.trust_state = "VERIFIED"  # type: ignore[misc]
    assert "trust_state" not in {
        f.name for f in dataclasses.fields(PolicyTargetBindingReferenceV2)
    }


# ======================================================================================
# The candidate carries ONE policy identity — D-5B1-1, condition 2
# ======================================================================================


def test_the_repaired_candidate_carries_the_whole_coordinate():
    """The happy path: what a consumer can now reconcile a verified proof against."""

    candidate = _build()
    coordinate = candidate.policy_coordinate_binding
    assert type(coordinate) is PolicyTargetBindingReferenceV2
    assert set(coordinate.policy_coordinate()) == set(POLICY_COORDINATE_COMPONENTS)
    assert coordinate.target_scope_digest == candidate.target_scope_digest
    assert candidate.policy_coordinate_binding_digest == coordinate.digest()


@pytest.mark.parametrize(
    "field,value",
    [("policy_id", "something.else-entirely"), ("policy_version", "99.0.0")],
)
def test_two_policy_references_naming_different_policies_are_refused(field, value):
    """The contradiction the pre-repair candidate could carry silently."""

    projection = build_projection()
    scope = build_target_scope(projection)
    binding = build_policy_binding(scope)
    with pytest.raises(PolicyTargetBindingError) as exc:
        _build(
            target_scope=scope,
            policy_binding=binding,
            policy_coordinate_binding=coordinate_for(binding, **{field: value}),
        )
    assert exc.value.reason is Reason.POLICY_COORDINATE_CONTENT_MISMATCH


def test_a_coordinate_bound_to_another_scope_is_refused():
    """A coordinate not tied to this scope could be transplanted onto another target."""

    projection = build_projection()
    ours = build_target_scope(projection)
    theirs = build_target_scope(projection, account_id="acct-999999999999")
    binding = build_policy_binding(ours)
    with pytest.raises(PolicyTargetBindingError) as exc:
        _build(
            target_scope=ours,
            policy_binding=binding,
            policy_coordinate_binding=build_policy_coordinate_binding(
                theirs,
                policy_id=binding.policy_id,
                policy_version=binding.policy_version,
            ),
        )
    assert exc.value.reason is Reason.POLICY_COORDINATE_CONTENT_MISMATCH


def test_a_missing_coordinate_is_refused_with_its_own_reason():
    """Required, not optional: an optional coordinate leaves the residual open by default."""

    projection = build_projection()
    scope = build_target_scope(projection)
    with pytest.raises(ExactTypeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection,
            decision=build_decision(projection),
            producer_attestation=build_attestation(
                recommendation_digest=projection.recommendation_digest
            ),
            policy_binding=build_policy_binding(scope),
            policy_coordinate_binding=None,
            target_scope=scope,
        )
    assert exc.value.reason is Reason.MISSING_POLICY_COORDINATE_BINDING


def test_a_v1_binding_cannot_stand_in_for_the_coordinate():
    """Exact types: the old reference is not a coordinate, which is the whole finding."""

    projection = build_projection()
    scope = build_target_scope(projection)
    binding = build_policy_binding(scope)
    with pytest.raises(ExactTypeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection,
            decision=build_decision(projection),
            producer_attestation=build_attestation(
                recommendation_digest=projection.recommendation_digest
            ),
            policy_binding=binding,
            policy_coordinate_binding=binding,
            target_scope=scope,
        )
    assert exc.value.reason is Reason.UNSUPPORTED_EXACT_TYPE
    assert type(binding) is PolicyTargetBindingReference


def test_substituting_the_coordinate_moves_the_candidate_digest():
    """The coordinate is inside the digest, so it cannot be swapped under a stale one."""

    projection = build_projection()
    scope = build_target_scope(projection)
    binding = build_policy_binding(scope)
    first = _build(target_scope=scope, policy_binding=binding)
    second = _build(
        target_scope=scope,
        policy_binding=binding,
        policy_coordinate_binding=coordinate_for(binding, policy_family="other-family"),
    )
    assert first.policy_coordinate_binding != second.policy_coordinate_binding
    assert first.candidate_digest != second.candidate_digest


def test_the_schema_version_is_the_second_binding_schema():
    """A new field set is a new schema identifier, not a silent widening of the old one."""

    assert POLICY_TARGET_BINDING_V2_SCHEMA_VERSION.endswith("-2")
    coordinate = _build().policy_coordinate_binding
    assert coordinate.schema_version == POLICY_TARGET_BINDING_V2_SCHEMA_VERSION
    with pytest.raises(PolicyTargetBindingError) as exc:
        dataclasses.replace(coordinate, schema_version="cloud-scaling-policy-target-binding-1")
    assert exc.value.reason is Reason.UNSUPPORTED_SCHEMA_VERSION
