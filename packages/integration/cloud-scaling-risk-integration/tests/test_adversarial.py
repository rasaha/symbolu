"""Adversarial coverage: substitution, smuggling, and non-canonical values.

Each test targets a **distinct tested property**, not a re-parametrization of one. The
substitution family below is deliberately exhaustive over the request's independent axes,
because ADR Amendment 3 makes the answer non-uniform: substituting a *routing* field
moves ``request_digest`` only and leaves ``subject_digest`` byte-identical, while
substituting a *subject* field moves both. A test suite that asserted "any change moves
subject_digest" would be asserting something false.
"""

from __future__ import annotations

import pytest

from conftest import build_recommendation
from risk_authority.integrations import (
    SeamContractError,
    SubjectBinding,
    SubjectContext,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)
from risk_authority.integrations.evaluation_contracts import SubjectBindingError
from ugence_cloud_scaling_controller.planning.recommendation import RecommendationError

from ugence_cloud_scaling_risk_integration import (
    ProjectionError,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    authenticate_controller_output,
    project_recommendation,
)

import ph_helpers as H


def project(rec):
    return project_recommendation(authenticate_controller_output(rec.to_canonical_dict()))


# --- unknown-field smuggling ------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("risk_class", "LOW"),
        ("policy_id", "policy-attacker"),
        ("control_results", [{"id": "X", "status": "PASS"}]),
        ("executable", True),
        ("authorization_envelope", {"signature": "forged"}),
        ("evaluation_time", "2026-01-01T00:00:00.000000Z"),
    ],
)
def test_unknown_field_smuggling_into_the_recommendation_fails_closed(recommendation, field, value):
    document = dict(recommendation.to_canonical_dict())
    document[field] = value
    with pytest.raises(RecommendationError, match="unknown recommendation field"):
        type(recommendation).from_dict(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "tnt-attacker"),
        ("subject_id", "wl-attacker"),
        ("evidence_references", ["sha256:" + "f" * 64]),
        ("policy_id", "policy-attacker"),
        ("executable", True),
    ],
)
def test_unknown_field_smuggling_into_the_subject_context_fails_closed(recommendation, field, value):
    canonical = dict(project(recommendation).context.to_canonical_dict())
    canonical[field] = value
    with pytest.raises(SeamContractError, match="unknown subject_context field"):
        SubjectContext.from_dict(canonical)


def test_unknown_field_smuggling_into_the_binding_fails_closed(recommendation):
    canonical = dict(project(recommendation).binding.to_canonical_dict())
    canonical["authority_granted"] = True
    with pytest.raises(SeamContractError, match="unknown subject_binding field"):
        SubjectBinding.from_dict(canonical)


def test_unknown_field_smuggling_into_the_request_fails_closed(recommendation):
    canonical = dict(project(recommendation).request.to_canonical_dict())
    canonical["risk_decision"] = "ALLOW"
    with pytest.raises(SeamContractError, match="unknown request field"):
        SubjectRiskEvaluationRequestV2.from_dict(canonical)


# --- substitution: subject-covered fields move BOTH digests ---------------------------------


def test_tenant_substitution_breaks_the_binding(recommendation):
    projection = project(recommendation)
    substituted = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(), "tenant_id": "tnt-attacker"}
    )
    assert substituted.digest() != projection.request_digest
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(substituted)


def test_subject_substitution_breaks_the_binding(recommendation):
    projection = project(recommendation)
    substituted = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(), "subject_id": "wl-attacker"}
    )
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(substituted)


def test_subject_type_substitution_breaks_the_binding(recommendation):
    projection = project(recommendation)
    substituted = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(),
         "subject_type": "cloud_scaling.capacity_action"}
    )
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(substituted)


def test_recommendation_digest_substitution_breaks_the_binding(recommendation):
    projection = project(recommendation)
    other = build_recommendation(predicted=12, recommendation_id="rec-other")
    substituted = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(),
         "recommendation_digest": other.digest()}
    )
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(substituted)


@pytest.mark.parametrize(
    "field,value",
    [
        ("action_type", "scale_down"),
        ("environment", "staging"),
        ("region", "us-east-1"),
        ("zone", "us-east-1a"),
        ("compute_group", "cluster-attacker"),
        ("resource_class", "batch"),
        ("magnitude_before", 999),
        ("magnitude_after", 999),
    ],
)
def test_context_substitution_with_a_stale_subject_digest_fails_closed(
    recommendation, field, value
):
    """The ADR §5.3 tamper demonstration, run over a real projection."""

    projection = project(recommendation)
    canonical = projection.request.to_canonical_dict()
    canonical["subject_context"] = {**canonical["subject_context"], field: value}
    # subject_digest is deliberately left stale.
    tampered = SubjectRiskEvaluationRequestV2.from_dict(canonical)
    assert tampered.subject_digest == projection.subject_digest
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(tampered)


# --- substitution: routing fields move ONLY request_digest (Amendment 3) --------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("requested_purpose", "cloud_scaling.other_purpose"),
        ("requested_domain", "other_domain"),
        ("requested_risk_class", "LOW"),
        ("evidence_references", ["sha256:" + "f" * 64]),
    ],
)
def test_routing_substitution_moves_request_digest_only(recommendation, field, value):
    """Amendment 3, pinned honestly: subject-digest equality is not whole-request
    authenticity. Asserting otherwise would overstate the guarantee."""

    projection = project(recommendation)
    substituted = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(), field: value}
    )
    assert substituted.digest() != projection.request_digest
    assert substituted.subject_digest == projection.subject_digest
    # ...so binding validation legitimately still passes; the control is elsewhere.
    validation = validate_subject_binding(substituted)
    assert validation.subject_digest == projection.subject_digest


def test_evidence_reordering_does_not_change_the_projected_request(recommendation):
    """Canonical ordering makes reordering a non-event, not a second identity."""

    projection = project(recommendation)
    assert projection.evidence_references == tuple(sorted(projection.evidence_references))
    reordered = tuple(reversed(projection.evidence_references))
    replayed = SubjectRiskEvaluationRequestV2.from_dict(
        {**projection.request.to_canonical_dict(),
         "evidence_references": list(sorted(reordered))}
    )
    assert replayed.digest() == projection.request_digest


def test_duplicate_evidence_references_are_deduplicated(recommendation):
    projection = project(recommendation)
    assert len(set(projection.evidence_references)) == len(projection.evidence_references)


# --- non-canonical values ---------------------------------------------------------------


def test_float_magnitude_is_rejected(recommendation):
    canonical = dict(project(recommendation).context.to_canonical_dict())
    canonical["magnitude_after"] = 9.0
    with pytest.raises(SeamContractError, match="not a float"):
        SubjectContext.from_dict(canonical)


def test_bool_as_int_magnitude_is_rejected(recommendation):
    canonical = dict(project(recommendation).context.to_canonical_dict())
    canonical["magnitude_before"] = True
    with pytest.raises(SeamContractError, match="not a bool"):
        SubjectContext.from_dict(canonical)


def test_non_utc_timestamp_string_is_rejected(recommendation):
    canonical = dict(project(recommendation).context.to_canonical_dict())
    canonical["subject_asserted_at"] = "2026-01-01T00:03:10+01:00"
    with pytest.raises(ValueError):
        SubjectContext.from_dict(canonical)


def test_naive_recommendation_time_is_rejected_not_assumed_utc():
    """A naive timestamp is ambiguous; assuming UTC would freeze a guess into the chain."""

    from datetime import datetime

    naive = datetime(2026, 1, 1, 0, 3, 10)
    rec = build_recommendation(recommendation_time=naive, recommendation_id="rec-naive")
    authenticated = authenticate_controller_output(rec.to_canonical_dict())
    with pytest.raises(ProjectionError, match="timezone-aware"):
        project_recommendation(authenticated)


def test_non_nfc_string_is_rejected_rather_than_silently_normalized():
    """NFC identity: the RA canonicalizer would normalize, changing the digested value."""

    import unicodedata

    # Built programmatically rather than typed as a literal, so the case cannot be
    # quietly lost to an editor or tool normalizing this source file.
    decomposed = unicodedata.normalize("NFD", "r\u00e9gion-1")
    assert decomposed != unicodedata.normalize("NFC", decomposed), (
        "the fixture must genuinely be in NFD form for this test to mean anything"
    )

    subject = H.subject()
    object.__setattr__(subject, "region", decomposed)
    rec = build_recommendation(subject=subject, recommendation_id="rec-nfd")
    authenticated = authenticate_controller_output(rec.to_canonical_dict())
    with pytest.raises(ProjectionError, match="NFC"):
        project_recommendation(authenticated)


def test_nfc_form_is_accepted_and_distinct_from_other_values():
    """The composed (NFC) form projects; a different region yields a different digest."""

    import unicodedata

    composed = unicodedata.normalize("NFC", "r\u00e9gion-1")
    accented = H.subject()
    object.__setattr__(accented, "region", composed)
    projected = project(build_recommendation(subject=accented, recommendation_id="rec-nfc"))
    assert projected.context.region == composed

    plain = H.subject()
    object.__setattr__(plain, "region", "region-1")
    assert project(
        build_recommendation(subject=plain, recommendation_id="rec-plain")
    ).context_digest != projected.context_digest


# --- missing required identity -------------------------------------------------------------


def test_missing_tenant_fails_closed():
    subject = H.subject(tenant_id=None)
    rec = build_recommendation(subject=subject, recommendation_id="rec-no-tenant")
    authenticated = authenticate_controller_output(rec.to_canonical_dict())
    with pytest.raises(ProjectionError, match="tenant_id"):
        project_recommendation(authenticated)


def test_an_unauthenticated_recommendation_cannot_be_projected(recommendation):
    """The projection refuses to accept a raw recommendation at its type boundary."""

    with pytest.raises(ProjectionError, match="AuthenticatedRecommendation"):
        project_recommendation(recommendation)


def test_subject_type_is_the_ratified_identifier_not_the_purpose(recommendation):
    """Regression guard for the one D-4 identifier ratified away from the proposal."""

    projection = project(recommendation)
    assert projection.request.subject_type == SUBJECT_TYPE_CAPACITY_SUBJECT
    assert projection.request.subject_type != projection.request.requested_purpose
