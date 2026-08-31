"""The TEV-2 input contract: expectations in, refusals out, never a verdict."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from _builders import (
    AS_OF,
    CONTENT_DIGEST,
    OTHER_DIGEST,
    identity,
    request,
    scope,
)
from ugence_trusted_evidence_authority.api import (
    EVIDENCE_TRUST_STAGE_ORDER,
    ApplicabilityDeclaration,
    EvidenceTrustStage,
    EvidenceVerificationRequest,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
)

R = TrustedEvidenceRefusalReason
UTC = timezone.utc


def test_declared_field_order_is_pinned():
    assert [f.name for f in dataclasses.fields(EvidenceVerificationRequest)] == [
        "evidence",
        "expected_content_digest",
        "expected_tenant_id",
        "expected_assessment_context_ref",
        "expected_assessment_context_digest",
        "expected_subject_ref",
        "expected_assessment_purpose_ref",
        "expected_usage_scope_ref",
        "as_of",
        "requested_trust_stages",
        "expected_assessed_system_binding_ref",
        "expected_assessed_system_binding_digest",
    ]


# --------------------------------------------------------------------------- #
# as_of — always explicit, never a clock
# --------------------------------------------------------------------------- #

def test_as_of_is_mandatory_with_no_default():
    field = {f.name: f for f in dataclasses.fields(EvidenceVerificationRequest)}["as_of"]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


def test_a_naive_as_of_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        request(as_of=datetime(2026, 6, 1))
    assert "timezone-aware" in str(excinfo.value)


def test_as_of_offset_equivalence_produces_one_digest():
    utc = AS_OF
    ist = AS_OF.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert request(as_of=utc).canonical_digest() == request(as_of=ist).canonical_digest()


def test_as_of_is_load_bearing():
    assert (
        request(as_of=AS_OF).canonical_digest()
        != request(as_of=AS_OF + timedelta(microseconds=1)).canonical_digest()
    )


# --------------------------------------------------------------------------- #
# requested_trust_stages — an order-irrelevant set, normalized canonically
# --------------------------------------------------------------------------- #

def test_stage_order_on_input_is_semantically_irrelevant():
    forward = request(
        requested_trust_stages=(
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
            EvidenceTrustStage.CURRENTLY_VALID,
        )
    )
    reversed_ = request(
        requested_trust_stages=(
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        )
    )
    assert forward == reversed_
    assert forward.canonical_bytes() == reversed_.canonical_bytes()
    assert forward.canonical_digest() == reversed_.canonical_digest()


def test_stages_are_normalized_into_the_ratified_adr_order():
    req = request(
        requested_trust_stages=[
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.PROVENANCE_VERIFIED,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        ]
    )
    assert req.requested_trust_stages == (
        EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        EvidenceTrustStage.PROVENANCE_VERIFIED,
        EvidenceTrustStage.CURRENTLY_VALID,
    )
    order = list(EVIDENCE_TRUST_STAGE_ORDER)
    assert req.requested_trust_stages == tuple(
        sorted(req.requested_trust_stages, key=order.index)
    )


def test_duplicate_stages_collapse_deterministically():
    req = request(
        requested_trust_stages=[
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.CURRENTLY_VALID,
        ]
    )
    assert req.requested_trust_stages == (EvidenceTrustStage.CURRENTLY_VALID,)


def test_a_set_input_is_accepted_and_normalized():
    req = request(
        requested_trust_stages={
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        }
    )
    assert req.requested_trust_stages == (
        EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        EvidenceTrustStage.CURRENTLY_VALID,
    )


def test_the_stored_stages_are_an_immutable_tuple():
    assert isinstance(request().requested_trust_stages, tuple)


def test_an_empty_stage_request_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        request(requested_trust_stages=())
    assert "at least one stage" in str(excinfo.value)


def test_requesting_policy_sufficiency_from_tap_is_refused():
    """ADR §12 — stage 6 is requirement-relative and never TAP's."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        request(requested_trust_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,))
    assert "requirement-relative" in str(excinfo.value)


def test_every_other_stage_is_requestable():
    for stage in EVIDENCE_TRUST_STAGE_ORDER:
        if stage is EvidenceTrustStage.POLICY_SUFFICIENT:
            continue
        assert request(requested_trust_stages=(stage,)).requested_trust_stages == (stage,)


@pytest.mark.parametrize("bad", ["CURRENTLY_VALID", 1, None, True])
def test_a_stage_lookalike_is_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        request(requested_trust_stages=(bad,))


@pytest.mark.parametrize("bad", ["abc", 5, None, {"a": 1}])
def test_a_non_collection_stage_argument_is_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        request(requested_trust_stages=bad)


# --------------------------------------------------------------------------- #
# Structural coordinate comparison — refusals only
# --------------------------------------------------------------------------- #

def test_matching_coordinates_yield_no_mismatches_and_that_is_not_a_pass():
    req = request()
    assert req.structural_scope_mismatches() == ()
    # ... and the request still reports that nothing was verified.
    assert (
        req.unperformed_verification_reason
        is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )
    assert req.evidence.unestablished_trust_stages
    assert req.evidence.authenticity_verified is False
    assert "not a pass" in EvidenceVerificationRequest.structural_scope_mismatches.__doc__


@pytest.mark.parametrize(
    "override,expected",
    [
        (dict(expected_content_digest=OTHER_DIGEST), R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH),
        (dict(expected_tenant_id="tenant-2"), R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        (dict(expected_assessment_context_ref="ctx-2"), R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        (dict(expected_assessment_context_digest=OTHER_DIGEST), R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        (dict(expected_subject_ref="subject-2"), R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        (dict(expected_assessed_system_binding_ref="bind-2"), R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH),
        (dict(expected_assessed_system_binding_digest=OTHER_DIGEST), R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH),
        (dict(expected_assessment_purpose_ref="purpose-forecast"), R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
        (dict(expected_usage_scope_ref="scope-evaluation-only"), R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
    ],
)
def test_each_coordinate_axis_produces_its_typed_refusal(override, expected):
    assert request(**override).structural_scope_mismatches() == (expected,)


def test_a_cross_tenant_replay_is_reported_as_a_tenant_mismatch():
    replayed = request(evidence=identity(scope=scope(tenant_id="tenant-2")))
    assert R.TRUSTED_EVIDENCE_TENANT_MISMATCH in replayed.structural_scope_mismatches()


def test_multiple_mismatches_are_returned_in_ratified_reason_order():
    req = request(
        expected_tenant_id="tenant-2",
        expected_content_digest=OTHER_DIGEST,
        expected_subject_ref="subject-2",
    )
    mismatches = req.structural_scope_mismatches()
    assert mismatches == (
        R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
        R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
        R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH,
    )
    order = list(R)
    assert list(mismatches) == sorted(mismatches, key=order.index)


def test_the_mismatch_sequence_is_deterministic_across_repeated_calls():
    req = request(expected_tenant_id="tenant-2", expected_subject_ref="subject-2")
    assert len({req.structural_scope_mismatches() for _ in range(20)}) == 1


def test_every_returned_value_is_a_refusal_reason():
    req = request(expected_tenant_id="tenant-2", expected_content_digest=OTHER_DIGEST)
    for reason in req.structural_scope_mismatches():
        assert isinstance(reason, R)


def test_a_system_independent_evidence_item_matches_empty_expectations():
    independent = identity(
        scope=scope(
            assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
            assessed_system_binding_ref="",
            assessed_system_binding_digest="",
        )
    )
    req = request(
        evidence=independent,
        expected_assessed_system_binding_ref="",
        expected_assessed_system_binding_digest="",
    )
    assert req.structural_scope_mismatches() == ()
    # But expecting a binding against system-independent evidence is a mismatch.
    assert R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH in request(
        evidence=independent
    ).structural_scope_mismatches()


# --------------------------------------------------------------------------- #
# Request construction invariants
# --------------------------------------------------------------------------- #

def test_the_expected_binding_reference_and_digest_are_co_required():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        request(expected_assessed_system_binding_digest="")
    assert "co-required" in str(excinfo.value)
    with pytest.raises(TrustedEvidenceContractError):
        request(expected_assessed_system_binding_ref="")


def test_the_evidence_must_be_the_exact_contract_type():
    class Fake:
        scope = None
        content_digest = CONTENT_DIGEST

    with pytest.raises(TrustedEvidenceContractError):
        request(evidence=Fake())


def test_blank_expected_coordinates_are_refused():
    for field in (
        "expected_tenant_id",
        "expected_assessment_context_ref",
        "expected_subject_ref",
        "expected_assessment_purpose_ref",
        "expected_usage_scope_ref",
    ):
        with pytest.raises(TrustedEvidenceContractError):
            request(**{field: "  "})


def test_the_request_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        request().expected_tenant_id = "tenant-2"


def test_the_request_carries_no_verdict_no_verifier_and_no_signature():
    names = {f.name for f in dataclasses.fields(EvidenceVerificationRequest)}
    for forbidden in (
        "verified",
        "status",
        "verification_status",
        "verifier_id",
        "verifier_authority",
        "key_id",
        "signature",
        "protocol_version",
        "verified_at",
        "receipt",
    ):
        assert forbidden not in names
