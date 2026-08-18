"""Backward compatibility: this additive package perturbs no frozen identity.

Phase 4C adds a new distribution and changes no Risk Authority or Cloud Scaling contract.
These tests pin that claim against the actual frozen values rather than asserting it in
prose, so a future edit to either dependency surfaces here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_authority.domain import RiskClass, Scope
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION,
    EVALUATION_REQUEST_SCHEMA_VERSION_V2,
    SUBJECT_BINDING_SCHEMA_VERSION,
    SUBJECT_CONTEXT_SCHEMA_VERSION,
    SUPPORTED_REQUEST_SCHEMA_VERSIONS,
    SubjectBinding,
    SubjectContext,
    SubjectRiskEvaluationRequest,
    SubjectRiskEvaluationRequestV2,
)

# The frozen identities, restated here from the Risk Authority conformance suite so this
# package fails independently if either ever moves.
FROZEN_V1_REQUEST_DIGEST = "sha256:88e9e559e860a637aa0a4389d2f0bc4597767b052dbe9b23a24d30dd09869809"
FROZEN_V2_REQUEST_DIGEST = "sha256:cd6dc88a3123959da32df7e03e936867416120099bdd303ebc954c6f04bdbcfb"
ADR_CONTEXT_DIGEST = "sha256:9af3f626a08e888a2916215a59c965e221179388ba3987cbbc6b2e0e64cfdbb0"
ADR_SUBJECT_DIGEST = "sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38"

T0 = datetime(2026, 8, 13, 4, 0, 0, tzinfo=timezone.utc)
REC_DIGEST = "sha256:" + "1" * 64


def adr_context() -> SubjectContext:
    return SubjectContext(
        action_type="scale_up",
        subject_asserted_at=T0,
        subject_valid_from=T0,
        subject_valid_until=T0 + timedelta(minutes=15),
        environment="prod",
        region="eu-west-1",
        zone=None,
        compute_group="cluster-7",
        resource_class="web",
        magnitude_before=6,
        magnitude_after=9,
    )


def test_frozen_v1_request_digest_is_unchanged():
    request = SubjectRiskEvaluationRequest(
        subject_type="cloud_scaling.capacity_action",
        subject_id="wl-checkout-api",
        subject_digest="sha256:" + "e" * 64,
        tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action",
        requested_domain="cloud_scaling",
        requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
        requested_risk_class=RiskClass.HIGH,
        evidence_references=("sha256:aaa", "sha256:bbb"),
        correlation_id="corr-42",
        idempotency_key="sha256:" + "2" * 64,
        evaluation_time=T0,
    )
    assert request.digest() == FROZEN_V1_REQUEST_DIGEST


def test_frozen_v2_request_digest_is_unchanged():
    request = SubjectRiskEvaluationRequestV2(
        subject_type="cloud_scaling.capacity_action",
        subject_id="wl-checkout-api",
        subject_digest=ADR_SUBJECT_DIGEST,
        tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action",
        requested_domain="cloud_scaling",
        requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
        evidence_references=("sha256:aaa", "sha256:bbb"),
        correlation_id="corr-42",
        subject_context=adr_context(),
        recommendation_digest=REC_DIGEST,
    )
    assert request.digest() == FROZEN_V2_REQUEST_DIGEST


def test_adr_worked_example_context_and_subject_digests_are_unchanged():
    context = adr_context()
    assert context.digest() == ADR_CONTEXT_DIGEST
    binding = SubjectBinding(
        tenant_id="tnt-acme",
        subject_id="wl-checkout-api",
        subject_type="cloud_scaling.capacity_action",
        recommendation_digest=REC_DIGEST,
        context_digest=ADR_CONTEXT_DIGEST,
    )
    assert binding.digest() == ADR_SUBJECT_DIGEST


def test_ratifying_a_new_subject_type_does_not_move_the_frozen_fixtures():
    """The D-4 subject-type ratification is additive, not a contract change.

    Risk Authority's frozen fixtures keep their own illustrative ``subject_type``; the
    adapter's ratified value is a *different* value it supplies on *its own* requests.
    Both coexist because ``subject_type`` is a caller-supplied string that Risk Authority
    never interprets, and the frozen digests above prove nothing moved.
    """

    from ugence_cloud_scaling_risk_integration import SUBJECT_TYPE_CAPACITY_SUBJECT

    assert SUBJECT_TYPE_CAPACITY_SUBJECT == "cloud_scaling.capacity_subject"
    ratified = SubjectBinding(
        tenant_id="tnt-acme",
        subject_id="wl-checkout-api",
        subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
        recommendation_digest=REC_DIGEST,
        context_digest=ADR_CONTEXT_DIGEST,
    )
    assert ratified.digest() != ADR_SUBJECT_DIGEST  # a different subject, as expected
    assert adr_context().digest() == ADR_CONTEXT_DIGEST  # ...and the context is untouched


def test_schema_tags_are_unchanged():
    assert EVALUATION_REQUEST_SCHEMA_VERSION == "risk-subject-evaluation-request-1"
    assert EVALUATION_REQUEST_SCHEMA_VERSION_V2 == "risk-subject-evaluation-request-2"
    assert SUBJECT_CONTEXT_SCHEMA_VERSION == "risk-subject-context-1"
    assert SUBJECT_BINDING_SCHEMA_VERSION == "risk-subject-binding-1"
    assert SUPPORTED_REQUEST_SCHEMA_VERSIONS == frozenset(
        {"risk-subject-evaluation-request-1", "risk-subject-evaluation-request-2"}
    )


def test_controller_recommendation_digest_behavior_is_unchanged(recommendation):
    """Round-trip stability of the controller's own identity is untouched by Phase 4C."""

    from ugence_cloud_scaling_controller.planning.recommendation import (
        CapacityActionRecommendation,
    )

    document = recommendation.to_canonical_dict()
    assert document["evidence_digest"] == recommendation.digest()
    rebuilt = CapacityActionRecommendation.from_dict(document)
    assert rebuilt.digest() == recommendation.digest()
    assert rebuilt.to_canonical_dict() == document


def test_risk_authority_and_controller_versions_meet_the_declared_floor():
    from risk_authority.version import __version__ as ra_version
    from ugence_cloud_scaling_controller.version import __version__ as csc_version

    def parts(value):
        return tuple(int(x) for x in value.split(".")[:3])

    assert parts(ra_version) >= (0, 4, 0), ra_version
    assert parts(csc_version) >= (0, 4, 0), csc_version
