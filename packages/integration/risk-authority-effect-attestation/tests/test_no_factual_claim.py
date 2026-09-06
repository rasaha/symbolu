"""A verified signature proves provenance and integrity, never that the effect is true.

These properties make the first bullet of the ADR's §4 mechanical: no field,
property, method or exported name can be read as a statement that the
observed effect occurred, and the permanent ``False`` cannot be flipped.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_risk_authority_effect_attestation as ea
from _fixtures import anchor_of, attestation, provider_signer, verifier, verify

#: Names that would read as a statement about the world. ``factual_correctness_established``
#: is the one deliberate exception: it exists to say ``False``.
FORBIDDEN_WORDS = ("effect_verified", "effect_true", "effect_occurred", "occurred", "matched",
                   "verified_effect", "truth", "is_true", "succeeded", "admitted",
                   "reconciled", "authorized", "approved")


def test_a_verified_result_never_claims_factual_correctness():
    result = verify(verifier(anchor_of(provider_signer())), attestation())
    assert result.outcome is ea.EffectAttestationVerificationOutcome.VERIFIED
    assert result.factual_correctness_established is False
    assert result.establishes == ea.EFFECT_ATTESTATION_ESTABLISHES == "PROVENANCE_AND_INTEGRITY_ONLY"
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        result.factual_correctness_established = True  # type: ignore[misc]
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        object.__setattr__(result, "establishes", "THE_EFFECT_IS_TRUE")
    assert result.factual_correctness_established is False


def test_no_result_field_property_or_method_reads_as_a_claim_about_the_world():
    names = {f.name for f in dataclasses.fields(ea.EffectAttestationVerificationResult)}
    names |= {n for n in dir(ea.EffectAttestationVerificationResult) if not n.startswith("_")}
    for name in names:
        for word in FORBIDDEN_WORDS:
            assert word not in name.lower(), name
    assert "factual_correctness_established" in names


def test_no_exported_name_reads_as_effect_truth_verification():
    for symbol in ea.__all__:
        lowered = symbol.lower()
        for word in ("effecttrue", "effect_true", "effectverified", "effect_verified", "truth",
                     "reconcil", "admit", "authoriz", "gateway", "connector"):
            assert word not in lowered, symbol


def test_the_role_sentences_disclaim_truth_for_both_roles():
    for role, sentence in ea.EFFECT_ATTESTER_ROLE_ESTABLISHES.items():
        assert "not" in sentence, role
    assert "not that the effect occurred" in ea.EFFECT_ATTESTER_ROLE_ESTABLISHES[
        ea.EffectAttesterRole.EXECUTING_PROVIDER]
    assert "not the truth of its observation" in ea.EFFECT_ATTESTER_ROLE_ESTABLISHES[
        ea.EffectAttesterRole.INDEPENDENT_OBSERVER]


def test_a_refused_result_also_never_claims_factual_correctness():
    result = verify(verifier(), attestation())
    assert result.outcome is ea.EffectAttestationVerificationOutcome.REFUSED
    assert result.factual_correctness_established is False
    assert result.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"


def test_the_outcome_vocabulary_has_exactly_two_members_and_no_optimistic_third():
    assert [m.name for m in ea.EffectAttestationVerificationOutcome] == ["VERIFIED", "REFUSED"]
    for banned in ("UNKNOWN", "PARTIAL", "PENDING", "BEST_EFFORT", "PROBABLY"):
        assert banned not in ea.EffectAttestationVerificationOutcome.__members__


def test_a_verified_result_cannot_be_constructed_without_the_anchor_revision_it_trusted():
    import dataclasses

    import pytest

    from _fixtures import anchor_of, attestation, provider_signer, verifier, verify

    verified = verify(verifier(anchor_of(provider_signer())), attestation())
    assert verified.outcome is ea.EffectAttestationVerificationOutcome.VERIFIED
    for missing in (None, "", "6d3c71b2"):
        with pytest.raises(ea.EffectAttestationContractError, match="anchor revision"):
            dataclasses.replace(verified, anchor_record_digest=missing)
    with pytest.raises(ea.EffectAttestationContractError):
        dataclasses.replace(verified, signing_payload_digest=None)
