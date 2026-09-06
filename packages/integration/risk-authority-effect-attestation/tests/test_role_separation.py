"""SE-2 and SE-4: two roles, two capabilities, nothing transfers.

A provider anchor never verifies as an observer and the inverse; an evidence,
receipt or Cloud Scaling anchor never verifies an effect; the role is inside
the signed bytes and inside the coordinate; and no verified result under the
provider role can be read as independent verification.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_risk_authority_effect_attestation as ea
from ugence_trusted_evidence_authority import TrustAnchorCapability, TrustAnchorRecord
from _fixtures import (
    OBSERVER,
    OBSERVER_ID,
    OBSERVER_KEY,
    PROVIDER,
    PROVIDER_ID,
    PROVIDER_KEY,
    anchor_of,
    attestation,
    observer_signer,
    provider_signer,
    verifier,
    verify,
)

R = ea.EffectAttestationRefusalReason
OUT = ea.EffectAttestationVerificationOutcome
CAP = TrustAnchorCapability


def test_the_two_roles_map_to_two_distinct_lent_capabilities_and_nothing_else():
    assert ea.capability_for_role(PROVIDER) is CAP.EFFECT_ATTESTATION_EXECUTING_PROVIDER
    assert ea.capability_for_role(OBSERVER) is CAP.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER
    assert set(ea.EFFECT_ATTESTER_ROLE_CAPABILITY.values()).isdisjoint(
        {CAP.EVIDENCE_PRODUCTION, CAP.RECEIPT_ISSUANCE, CAP.CLOUD_SCALING_RECOMMENDATION_ATTESTATION}
    )
    with pytest.raises(ea.EffectAttestationContractError):
        ea.capability_for_role("EXECUTING_PROVIDER")  # a string spelling a member is not one


def test_a_provider_anchor_used_as_an_independent_observer_refuses_and_the_inverse():
    """Same identity, same key id, same key — installed under the other role's capability."""

    provider = provider_signer()
    provider_as_observer = TrustAnchorRecord(
        **{**_fields(anchor_of(provider)), "capability": CAP.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER}
    )
    # The provider's genuine attestation, verified as if by an observer: the coordinate
    # names the observer capability, where only the wrongly-filed anchor sits — and the
    # role inside the signed bytes still says PROVIDER, so the role check refuses first.
    att = attestation(provider)
    result = verify(verifier(provider_as_observer), att, role=OBSERVER)
    assert result.refusal_reason is R.ROLE_MISMATCH
    # A wrapper re-labelled to the observer role over the provider's signature: the
    # payload changes, so the signature no longer verifies under the mis-filed anchor.
    relabelled = dataclasses.replace(att, attester_role=OBSERVER)
    result = verify(verifier(provider_as_observer), relabelled, role=OBSERVER)
    assert result.refusal_reason is R.SIGNATURE_INVALID
    # And the correctly-filed provider anchor never answers an observer coordinate.
    result = verify(verifier(anchor_of(provider)), relabelled, role=OBSERVER)
    assert result.refusal_reason is R.ANCHOR_UNKNOWN

    observer = observer_signer()
    observer_as_provider = TrustAnchorRecord(
        **{**_fields(anchor_of(observer)), "capability": CAP.EFFECT_ATTESTATION_EXECUTING_PROVIDER}
    )
    att = attestation(observer)
    assert verify(verifier(observer_as_provider), att, role=PROVIDER).refusal_reason is R.ROLE_MISMATCH
    relabelled = dataclasses.replace(att, attester_role=PROVIDER)
    assert verify(verifier(observer_as_provider), relabelled, role=PROVIDER).refusal_reason is R.SIGNATURE_INVALID
    assert verify(verifier(anchor_of(observer)), relabelled, role=PROVIDER).refusal_reason is R.ANCHOR_UNKNOWN


def test_a_signer_re_keyed_for_the_other_role_verifies_only_under_that_role():
    """The honest case: the same key legitimately provisioned under both roles is two
    anchor records, and each attestation verifies only under the role it was signed for."""

    as_provider = provider_signer()
    as_observer = provider_signer(attester_role=OBSERVER)
    v = verifier(anchor_of(as_provider), anchor_of(as_observer))
    assert verify(v, attestation(as_provider), role=PROVIDER).outcome is OUT.VERIFIED
    assert verify(v, attestation(as_observer), role=OBSERVER).outcome is OUT.VERIFIED
    assert verify(v, attestation(as_provider), role=OBSERVER).refusal_reason is R.ROLE_MISMATCH
    assert verify(v, attestation(as_observer), role=PROVIDER).refusal_reason is R.ROLE_MISMATCH


@pytest.mark.parametrize(
    "foreign",
    [CAP.EVIDENCE_PRODUCTION, CAP.RECEIPT_ISSUANCE, CAP.CLOUD_SCALING_RECOMMENDATION_ATTESTATION],
    ids=["evidence-producer", "receipt-issuer", "producer-attester"],
)
def test_an_evidence_receipt_or_producer_attester_anchor_never_verifies_an_effect(foreign):
    """The same key, filed under a foreign purpose, is not at the effect coordinate."""

    provider = provider_signer()
    foreign_anchor = TrustAnchorRecord(**{**_fields(anchor_of(provider)), "capability": foreign})
    result = verify(verifier(foreign_anchor), attestation(provider))
    assert result.refusal_reason is R.ANCHOR_UNKNOWN
    # Even a directory that lies about the coordinate cannot pass a foreign capability.
    class LiesAboutTheCoordinate:
        def resolve(self, coordinate, *, as_of=None):
            return ea.TrustAnchorResolution.resolved(foreign_anchor.coordinate, foreign_anchor)

    v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=LiesAboutTheCoordinate())
    assert verify(v, attestation(provider)).refusal_reason is R.ANCHOR_COORDINATE_MISMATCH


def test_the_role_is_inside_the_signed_bytes_and_inside_the_coordinate():
    att = attestation()
    payload = att.signing_payload()
    assert payload["attester_role"] == "EXECUTING_PROVIDER"
    assert "attester_role" in ea.EFFECT_ATTESTATION_SIGNED_FIELDS
    coordinate = ea.effect_attester_coordinate(
        role=PROVIDER, attester_identity=PROVIDER_ID, attester_key_id=PROVIDER_KEY
    )
    assert coordinate.capability is CAP.EFFECT_ATTESTATION_EXECUTING_PROVIDER
    other = ea.effect_attester_coordinate(
        role=OBSERVER, attester_identity=PROVIDER_ID, attester_key_id=PROVIDER_KEY
    )
    assert coordinate != other
    assert ea.anchor_coordinate_digest(coordinate) != ea.anchor_coordinate_digest(other)


def test_a_verified_provider_attestation_is_not_independent_verification():
    result = verify(verifier(anchor_of(provider_signer())), attestation())
    assert result.outcome is OUT.VERIFIED
    assert result.attester_role is PROVIDER
    assert "not independent verification" in result.role_establishes
    assert "not that the effect occurred" in result.role_establishes
    observer = observer_signer()
    result = verify(verifier(anchor_of(observer)), attestation(observer), role=OBSERVER)
    assert result.outcome is OUT.VERIFIED
    assert "not the truth of its observation" in result.role_establishes


def test_the_reference_signer_publishes_only_under_its_own_role():
    assert anchor_of(provider_signer()).capability is CAP.EFFECT_ATTESTATION_EXECUTING_PROVIDER
    assert anchor_of(observer_signer()).capability is CAP.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER
    assert anchor_of(observer_signer()).authority_id == OBSERVER_ID
    assert anchor_of(observer_signer()).key_id == OBSERVER_KEY


def _fields(anchor: TrustAnchorRecord) -> dict:
    return {f.name: getattr(anchor, f.name) for f in dataclasses.fields(anchor)}
