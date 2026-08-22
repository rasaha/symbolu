"""F-5: what the Phase 4C chain actually does with the recommendation ID.

The corrected statement, which these tests demonstrate rather than assert in prose:

> The recommendation ID **is transitively bound** by the Phase 4C canonical digest chain,
> but it is **not directly recoverable** from the resulting digest and is **not exposed as
> an independently cross-checkable decision field**.

An earlier revision of this package claimed the chain "carries no recommendation id". That
was wrong — changing the ID changes ``recommendation_digest`` — and the wrong claim made
Phase 5A's binding look weaker than it is. The Phase 5A *conclusion* is unaffected: the ID
is carried explicitly, it must reconcile, the producer attestation binds it under signature,
and only Phase 5B can decide whether that signature is genuine.
"""

from __future__ import annotations

import pytest

from conftest import (
    build_attestation,
    build_decision,
    build_policy_binding,
    build_projection,
    build_recommendation,
    build_target_scope,
    coordinate_for,
)
from ugence_cloud_scaling_authorization_contracts import (
    PHASE_5A_TRUST_STATE,
    ProducerAttestationError,
    build_capacity_authorization_candidate,
)


def test_changing_the_recommendation_id_changes_the_phase4_digests():
    """Transitively bound: the ID is inside the bytes the chain hashes."""

    a = build_projection(build_recommendation(recommendation_id="rec-phase5a-1"))
    b = build_projection(build_recommendation(recommendation_id="rec-substituted"))
    assert a.recommendation_digest != b.recommendation_digest
    # and it propagates through the whole chain
    assert a.request_digest != b.request_digest


def test_the_id_is_not_recoverable_from_the_digest():
    """Bound is not the same as readable. sha256 is not reversible, and no field holds it.

    This is precisely why Phase 5A cannot cross-check a supplied ID against Phase 4: there
    is nothing to compare it *to*, even though the digest commits to it.
    """

    from risk_authority.integrations import SubjectContext

    projection = build_projection()
    assert "recommendation_id" not in SubjectContext.__dataclass_fields__
    assert "recommendation_id" not in type(projection).__dataclass_fields__
    # The digest is an opaque 64-hex value; the ID cannot be read back out of it.
    assert "rec-phase5a-1" not in projection.recommendation_digest


def test_a_stale_digest_paired_with_a_changed_id_fails():
    """Substituting the ID while keeping the old digest is caught by the binding check."""

    projection = build_projection()
    # An attestation whose ID was swapped but which still claims the original digest is
    # structurally admissible on its own — the ID is not cross-checkable — but it no longer
    # describes the recommendation whose chain was actually re-derived.
    other = build_projection(build_recommendation(recommendation_id="rec-substituted"))
    stale = build_attestation(
        recommendation_id="rec-substituted",
        recommendation_digest=projection.recommendation_digest,  # stale: belongs to the original
    )
    decision = build_decision(other)
    scope = build_target_scope(other)
    with pytest.raises(ProducerAttestationError) as exc:
        build_capacity_authorization_candidate(
            projection=other,
            decision=decision,
            producer_attestation=stale,
            policy_binding=build_policy_binding(scope),
            policy_coordinate_binding=coordinate_for(build_policy_binding(scope)),
            target_scope=scope,
        )
    assert exc.value.reason.value == "producer_attestation_content_mismatch"


def test_the_id_is_covered_by_the_producer_signing_payload():
    """The ID sits inside the signed bytes, so Phase 5B can detect a substitution."""

    projection = build_projection()
    a = build_attestation(
        recommendation_digest=projection.recommendation_digest, recommendation_id="rec-phase5a-1"
    )
    b = build_attestation(
        recommendation_digest=projection.recommendation_digest, recommendation_id="rec-other"
    )
    assert "recommendation_id" in a.signing_payload()
    assert a.signing_payload_digest != b.signing_payload_digest


def test_the_id_reaches_the_candidate_digest():
    """And a substituted ID moves the candidate digest, so it cannot ride along silently."""

    projection = build_projection()
    decision = build_decision(projection)
    scope = build_target_scope(projection)
    policy = build_policy_binding(scope)

    def _build(recommendation_id):
        return build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=build_attestation(
                recommendation_digest=projection.recommendation_digest,
                recommendation_id=recommendation_id,
            ),
            policy_binding=policy,
            policy_coordinate_binding=coordinate_for(policy),
            target_scope=scope,
        )

    assert _build("rec-phase5a-1").candidate_digest != _build("rec-other").candidate_digest


def test_a_self_consistent_but_unverified_attestation_remains_non_authoritative():
    """The limit of F-5: internal consistency is not authenticity.

    An attacker who controls the producer key material can mint an attestation that is
    perfectly self-consistent — correct ID, correct digest, correct signing purpose, a real
    signature. Phase 5A admits it structurally, and must, because it verifies no signature.
    What it must never do is call the result trusted. It does not: the trust state stays
    ``PRESENT_BUT_NOT_TRUST_VERIFIED`` and the candidate grants nothing.
    """

    projection = build_projection()
    decision = build_decision(projection)
    scope = build_target_scope(projection)
    rogue = build_attestation(
        recommendation_digest=projection.recommendation_digest,
        producer_id="attacker.impersonating-controller",
        producer_key_id="attacker-key-1",
    )
    candidate = build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=rogue,
        policy_binding=build_policy_binding(scope),
        policy_coordinate_binding=coordinate_for(build_policy_binding(scope)),
        target_scope=scope,
    )
    # Structurally admissible...
    assert candidate.producer_id == "attacker.impersonating-controller"
    # ...and still worth nothing.
    assert candidate.producer_attestation.trust_state is PHASE_5A_TRUST_STATE
    assert candidate.trust_state.value == "PRESENT_BUT_NOT_TRUST_VERIFIED"
    assert candidate.grants_authority is False
    # The rogue producer identity is inside the digest, so Phase 5B sees exactly who signed.
    assert candidate.digest_payload()["producer_attestation"]["producer_id"] == (
        "attacker.impersonating-controller"
    )
