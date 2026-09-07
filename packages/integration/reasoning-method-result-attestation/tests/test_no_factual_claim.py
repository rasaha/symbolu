"""A verified signature proves provenance and integrity, never that the comparison
is correct or that any method is fit.

These properties make the ADR's role sentence mechanical: no field, property,
method or exported name can be read as a statement about fitness or correctness,
and the permanent ``False`` cannot be flipped.
"""

from __future__ import annotations

import dataclasses

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import anchor_of, engine_signer, signed, verifier, verify

#: Names that would read as a statement about the comparison. ``factual_correctness_established``
#: is the one deliberate exception: it exists to say ``False``.
FORBIDDEN_WORDS = ("correct", "fit_", "is_fit", "sufficient", "admitted", "admission", "qualif",
                   "truth", "is_true", "succeeded", "authorized", "approved", "verified_result",
                   "result_verified", "recommend")


def test_a_verified_result_never_claims_factual_correctness():
    r = verify(verifier(anchor_of(engine_signer())), signed())
    assert r.outcome is ra.ComparisonResultVerificationOutcome.VERIFIED
    assert r.factual_correctness_established is False
    assert r.establishes == ra.COMPARISON_RESULT_ATTESTATION_ESTABLISHES == "PROVENANCE_AND_INTEGRITY_ONLY"
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        r.factual_correctness_established = True  # type: ignore[misc]
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        object.__setattr__(r, "establishes", "THE_COMPARISON_IS_CORRECT")
    assert r.factual_correctness_established is False


def test_no_result_field_property_or_method_reads_as_a_claim_about_the_comparison():
    names = {f.name for f in dataclasses.fields(ra.ComparisonResultVerificationResult)}
    names |= {n for n in dir(ra.ComparisonResultVerificationResult) if not n.startswith("_")}
    for name in names - {"factual_correctness_established"}:
        for word in FORBIDDEN_WORDS:
            assert word not in name.lower(), name
    assert "factual_correctness_established" in names


def test_no_exported_name_reads_as_correctness_or_fitness_or_admission():
    for symbol in ra.__all__:
        lowered = symbol.lower()
        for word in ("correct", "fitness", "is_fit", "admit", "admission", "authoriz", "gateway",
                     "connector", "recommend", "select", "truth"):
            assert word not in lowered, symbol


def test_the_role_sentence_disclaims_correctness():
    for role, sentence in ra.COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES.items():
        assert "not" in sentence, role
    assert "not that the comparison is correct" in ra.COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES[
        ra.ComparisonResultAttesterRole.COMPARISON_ENGINE]


def test_a_refused_result_also_never_claims_factual_correctness():
    r = verify(verifier(), signed())
    assert r.outcome is ra.ComparisonResultVerificationOutcome.REFUSED
    assert r.factual_correctness_established is False
    assert r.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"


def test_the_outcome_vocabulary_has_exactly_two_members_and_no_optimistic_third():
    assert [m.name for m in ra.ComparisonResultVerificationOutcome] == ["VERIFIED", "REFUSED"]
    for banned in ("UNKNOWN", "PARTIAL", "PENDING", "BEST_EFFORT", "PROBABLY"):
        assert banned not in ra.ComparisonResultVerificationOutcome.__members__


def test_a_verified_result_cannot_be_constructed_without_the_anchor_revision_it_trusted():
    verified = verify(verifier(anchor_of(engine_signer())), signed())
    assert verified.outcome is ra.ComparisonResultVerificationOutcome.VERIFIED
    for missing in (None, "", "6d3c71b2"):
        with pytest.raises(ra.ComparisonResultAttestationContractError, match="anchor revision"):
            dataclasses.replace(verified, anchor_record_digest=missing)
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        dataclasses.replace(verified, signing_payload_digest=None)
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="bare 64-hex"):
        dataclasses.replace(verified, result_digest="sha256:" + "a" * 64)
