"""Why each member of the recorded half is there — measured, not asserted in prose.

A fact belongs in the recorded half when nothing established it. That is a claim about the
code, so each member gets a test that *demonstrates the gap*: an artifact still mints
``VERIFIED`` while carrying a value nobody checked. These tests would be alarming if the
field were in the verified half. That is the point — they are the evidence for the partition,
and if one of them ever starts failing because something began checking the fact, the fact
should be promoted.
"""

from __future__ import annotations

import json

import pytest

from _policy_fixtures import T_MID, issued, port_for, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityOutcome as O,
    PolicyAuthenticityVerifier,
    VerifiedPolicyArtifactIntegrityError,
)
from ugence_cloud_scaling_policy_authenticity.verified import (
    RECORDED_FACT_NAMES,
    VERIFIED_FACT_NAMES,
)


# --------------------------------------------------------------------------- #
# policy_type — not signature-covered, and never compared at resolution
# --------------------------------------------------------------------------- #
@pytest.mark.invariant
def test_policy_type_is_absent_from_the_signed_issuance_payload():
    """Measured off a genuine record, not read off the ADR. ``adapter_id`` is there; this is not."""

    _authority, record = issued()
    _prefix, _sep, body = record.signing_payload().partition(b"\x00")
    signed_keys = set(json.loads(body.decode()))

    assert "adapter_id" in signed_keys
    assert "policy_body_digest" in signed_keys
    assert "policy_type" not in signed_keys


@pytest.mark.adversarial
def test_a_record_differing_only_in_policy_type_is_now_refused():
    """The gap, closed (5B-3, R-8). Kept in place and **inverted** rather than deleted.

    This test used to assert the opposite — that a substituted ``policy_type`` still minted
    ``VERIFIED`` — and that assertion was the honest record of why the fact sat in the
    recorded half: the signature does not cover it, ``resolve_policy`` recomputes the body
    digest from the *descriptor's* policy type rather than the record's, and this package
    held no adapter registry with which to re-derive the descriptor. The value was
    transitively committed inside ``policy_body_digest``, whose frame includes it, but a hash
    is one-way and there was no pre-image to check against.

    Route 1 supplied the pre-image: the resolution now publishes the descriptor's projection,
    so gate 14 reframes ``(adapter_id, policy_type, projection)`` and compares the result
    against the digest the issuance signature covered. Substituting the record's policy type
    makes the record and the published projection disagree, and the determination is refused.

    Inverting the assertion in place is deliberate: the file still measures the same
    substitution, so a regression restores the old behaviour and fails here rather than
    quietly passing a suite that no longer looks.
    """

    authority, record = issued()
    object.__setattr__(record, "policy_type", "SomethingElseEntirely")
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_DIGEST_MISMATCH
    assert result.verified_policy is None


@pytest.mark.invariant
def test_policy_type_is_verified_and_reachable_through_the_verified_accessor():
    """The other half of the promotion: the accessor now answers instead of refusing."""

    _authority, _record = issued()
    artifact = _verified()
    assert "policy_type" in VERIFIED_FACT_NAMES
    assert "policy_type" not in RECORDED_FACT_NAMES
    assert "policy_type" not in artifact.recorded_facts()
    assert artifact.verified_fact("policy_type") == artifact.policy_type


# --------------------------------------------------------------------------- #
# trust_configuration_digest — self-reported by the port
# --------------------------------------------------------------------------- #
class LyingWrapperPort:
    """Delegates every resolution to a genuine port while reporting an arbitrary identity.

    Indistinguishable from the genuine port at this boundary: the resolutions it returns are
    real, and the trust identity is the one thing the verifier cannot cross-check, because the
    port *is* the seam to the authority. Any check would be the port vouching for itself.
    """

    is_production_authoritative = True

    def __init__(self, inner, reported: str):
        self._inner = inner
        self._reported = reported

    @property
    def trust_configuration_digest(self) -> str:
        return self._reported

    def resolve_policy_version(self, **kwargs):
        return self._inner.resolve_policy_version(**kwargs)


@pytest.mark.adversarial
def test_a_wrapper_port_can_report_any_well_formed_trust_identity():
    """The gap itself, and the reason the fact cannot sit in the verified half."""

    authority, record = issued()
    lying = LyingWrapperPort(port_for(authority), reported="f" * 64)
    result = PolicyAuthenticityVerifier(resolution_port=lying).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.VERIFIED
    assert result.verified_policy.trust_configuration_digest == "f" * 64


@pytest.mark.invariant
def test_the_trust_identity_is_recorded_and_refused_by_the_verified_accessor():
    artifact = _verified()
    assert "trust_configuration_digest" in RECORDED_FACT_NAMES
    assert "trust_configuration_digest" not in VERIFIED_FACT_NAMES
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        artifact.verified_fact("trust_configuration_digest")


@pytest.mark.invariant
def test_a_recorded_fact_is_still_covered_by_the_artifact_digest():
    """Unverified is not unprotected: nobody checked it, and nobody can rewrite it either."""

    from ugence_cloud_scaling_policy_authenticity import (
        require_verified_policy_authenticity,
    )

    for name, substitute in (
        ("policy_type", "RewrittenAfterTheFact"),
        ("trust_configuration_digest", "e" * 64),
    ):
        artifact = _verified()
        object.__setattr__(artifact, name, substitute)
        with pytest.raises(VerifiedPolicyArtifactIntegrityError):
            require_verified_policy_authenticity(artifact)


def _verified():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy
