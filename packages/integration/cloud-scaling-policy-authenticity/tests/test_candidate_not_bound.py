"""ADR residual R-4, stated as executable behaviour rather than as a caveat.

A verified policy proof is **not** bound to any candidate. A candidate may be supplied and its
digest recorded as the scope of the determination — which candidate this proof accompanied —
and nothing about it is reconciled. The consequence, measured here rather than described: one
genuine policy proof verifies alongside any candidate whatsoever, including one whose policy
binding names an entirely different policy.

Why the verifier cannot do better at this phase
------------------------------------------------
D-5B0B-3 measured that ``PolicyTargetBindingReference`` carries three of the coordinate's six
components (``policy_family``, ``scope`` and ``tenant_id`` are absent) and that its fourth,
``policy_artifact_digest``, requires a ``sha256:`` prefix no Policy Authority digest carries.
A Phase 5A binding therefore cannot name a coordinate, so there is no coordinate in the
candidate to compare against the one that was verified. Binding the two is 5B-1's
decision-scope repair, and pretending to do it here — by reconciling the two components that
do exist — would read as a binding while establishing far less than one.

These tests skip outside a checkout, where the Phase 5A test tree that builds a genuine
candidate is unavailable.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, genuine_candidate, issued, phase5a_builders, verifier_for
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome as O

pytestmark = pytest.mark.skipif(
    phase5a_builders() is None,
    reason="the Phase 5A test tree is unavailable outside a source checkout",
)


def _verify(candidate=None):
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
        candidate=candidate,
    )


def _candidate_naming_another_policy():
    """A genuine Phase 5A candidate whose policy binding names a different policy entirely."""

    builders = phase5a_builders()
    from ugence_cloud_scaling_authorization_contracts import (
        build_capacity_authorization_candidate,
    )

    projection = builders.build_projection()
    decision = builders.build_decision(projection)
    attestation = builders.build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    scope = builders.build_target_scope(projection)
    binding = builders.build_policy_binding(
        scope, policy_id="something.else-entirely", policy_version="99.0.0"
    )
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=binding,
        # Both references name the other policy: since 5B-1 a candidate cannot carry two
        # policy identities, so "a candidate about a different policy" means both halves.
        policy_coordinate_binding=builders.build_policy_coordinate_binding(
            scope, policy_id="something.else-entirely", policy_version="99.0.0"
        ),
        target_scope=scope,
    )


@pytest.mark.happy
def test_a_candidate_is_optional_and_its_absence_is_not_a_refusal():
    result = _verify(candidate=None)
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.candidate_digest_fact is None


@pytest.mark.happy
def test_a_supplied_candidate_is_recorded_as_the_scope_of_the_determination():
    candidate = genuine_candidate()
    result = _verify(candidate=candidate)
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.candidate_digest_fact == candidate.candidate_digest


@pytest.mark.adversarial
def test_one_policy_proof_verifies_alongside_a_candidate_naming_a_different_policy():
    """The R-4 residual, measured. Read a VERIFIED here as saying nothing about the candidate."""

    other = _candidate_naming_another_policy()
    result = _verify(candidate=other)
    assert result.outcome is O.VERIFIED
    # Nothing about the binding was compared, and nothing could have been.
    assert other.policy_binding.policy_id != result.verified_policy.policy_id
    assert result.verified_policy.candidate_digest_fact == other.candidate_digest


@pytest.mark.adversarial
def test_the_candidate_digest_is_recorded_in_a_different_namespace_and_never_converted():
    """D-5B0B-2 made executable: the candidate's digest cannot be a Policy Authority digest."""

    from ugence_cloud_scaling_policy_authenticity import is_phase5a_digest, is_policy_digest

    verified = _verify(candidate=genuine_candidate()).verified_policy
    assert is_phase5a_digest(verified.candidate_digest_fact)
    assert not is_policy_digest(verified.candidate_digest_fact)
    assert is_policy_digest(verified.policy_body_digest)
    assert not is_phase5a_digest(verified.policy_body_digest)


@pytest.mark.adversarial
def test_two_determinations_differing_only_in_candidate_are_two_determinations():
    """The candidate is not signature-covered, but it IS artifact-digest covered.

    So the proof cannot be silently re-pointed at another candidate after the fact, even
    though it was never bound to the one it names.
    """

    first = _verify(candidate=genuine_candidate()).verified_policy
    second = _verify(candidate=_candidate_naming_another_policy()).verified_policy
    assert first.candidate_digest_fact != second.candidate_digest_fact
    assert first.artifact_digest != second.artifact_digest
    assert first.policy_body_digest == second.policy_body_digest
