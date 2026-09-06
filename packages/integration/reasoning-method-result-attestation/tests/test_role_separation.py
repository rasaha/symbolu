"""SCR-1: one role, one lent capability, nothing transfers.

An evidence, receipt, Cloud Scaling, effect or set-publication anchor never
verifies a comparison result; the role is inside the signed bytes and inside the
coordinate; a string spelling a role is not a role; and the independent-verifier
role is absent by design.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_reasoning_method_result_attestation as ra
from ugence_trusted_evidence_authority import TrustAnchorCapability, TrustAnchorRecord
from _fixtures import ENGINE, ENGINE_ID, ENGINE_KEY, anchor_of, engine_signer, signed, verifier, verify

R = ra.ComparisonResultRefusalReason
OUT = ra.ComparisonResultVerificationOutcome
CAP = TrustAnchorCapability
FOREIGN = [c for c in CAP if c is not CAP.COMPARISON_RESULT_ATTESTATION]


def test_the_one_role_maps_to_the_one_lent_capability_and_nothing_else():
    assert ra.capability_for_role(ENGINE) is CAP.COMPARISON_RESULT_ATTESTATION
    assert [m.name for m in ra.ComparisonResultAttesterRole] == ["COMPARISON_ENGINE"]
    assert set(ra.COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY.values()).isdisjoint(set(FOREIGN))
    assert len(FOREIGN) == 6
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.capability_for_role("COMPARISON_ENGINE")  # a string spelling a member is not one


def test_no_independent_verifier_role_exists_in_this_slice():
    """ADR §3: a second signature by a party that re-ran the comparison is a later
    slice with its own role; nothing here can be mistaken for it."""

    for member in ra.ComparisonResultAttesterRole:
        assert "VERIFIER" not in member.name and "INDEPENDENT" not in member.name and "OBSERVER" not in member.name


@pytest.mark.parametrize("foreign", FOREIGN, ids=[c.name.lower() for c in FOREIGN])
def test_a_foreign_capability_anchor_never_verifies_a_comparison_result(foreign):
    """The same key, filed under a foreign purpose, is not at the engine coordinate."""

    signer = engine_signer()
    foreign_anchor = TrustAnchorRecord(**{**_fields(anchor_of(signer)), "capability": foreign})
    r = verify(verifier(foreign_anchor), signed(signer))
    assert r.refusal_reason is R.ANCHOR_UNKNOWN

    # Even a directory that lies about the coordinate cannot pass a foreign capability.
    class LiesAboutTheCoordinate:
        def resolve(self, coordinate, *, as_of=None):
            return ra.TrustAnchorResolution.resolved(foreign_anchor.coordinate, foreign_anchor)

    v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=LiesAboutTheCoordinate())
    assert verify(v, signed(signer)).refusal_reason is R.ANCHOR_COORDINATE_MISMATCH


def test_the_role_is_inside_the_signed_bytes_and_inside_the_coordinate():
    sr = signed()
    assert sr.signing_payload()["signer_role"] == "COMPARISON_ENGINE"
    assert "signer_role" in ra.COMPARISON_RESULT_SIGNED_FIELDS
    coordinate = ra.comparison_result_signer_coordinate(role=ENGINE, signer_identity=ENGINE_ID, signer_key_id=ENGINE_KEY)
    assert coordinate.capability is CAP.COMPARISON_RESULT_ATTESTATION
    other = ra.TrustAnchorCoordinate(authority_id=ENGINE_ID, key_id=ENGINE_KEY,
                                     capability=CAP.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER)
    assert coordinate != other
    assert ra.anchor_coordinate_digest(coordinate) != ra.anchor_coordinate_digest(other)


def test_a_role_that_is_not_the_member_is_refused_at_every_seam():
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        dataclasses.replace(signed(), signer_role="COMPARISON_ENGINE")
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        verify(verifier(anchor_of(engine_signer())), signed(), role="COMPARISON_ENGINE")
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        engine_signer(signer_role="COMPARISON_ENGINE")


def test_a_verified_engine_signature_is_not_a_statement_that_the_comparison_is_correct():
    r = verify(verifier(anchor_of(engine_signer())), signed())
    assert r.outcome is OUT.VERIFIED
    assert r.signer_role is ENGINE
    assert "not that the comparison is correct" in r.role_establishes
    assert "not that any method is fit" in r.role_establishes


def test_the_reference_signer_publishes_only_under_its_own_role():
    anchor = anchor_of(engine_signer())
    assert anchor.capability is CAP.COMPARISON_RESULT_ATTESTATION
    assert anchor.authority_id == ENGINE_ID and anchor.key_id == ENGINE_KEY


def _fields(anchor: TrustAnchorRecord) -> dict:
    return {f.name: getattr(anchor, f.name) for f in dataclasses.fields(anchor)}
