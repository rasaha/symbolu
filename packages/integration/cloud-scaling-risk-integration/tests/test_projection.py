"""Happy-path conformance for the deterministic recommendation → v2 request projection.

The adversarial counterparts live in ``test_adversarial.py``, ``test_authenticity.py``,
``test_time_authority.py`` and ``test_gate_removal_probes.py``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import build_recommendation, recommendation_for
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION_V2,
    SUBJECT_BINDING_SCHEMA_VERSION,
    SUBJECT_CONTEXT_SCHEMA_VERSION,
    SubjectBinding,
    SubjectContext,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)
from ugence_cloud_scaling_controller.planning.candidates import ActionKind

from ugence_cloud_scaling_risk_integration import (
    CANONICAL_ACTION_TYPES,
    DOMAIN_CLOUD_SCALING,
    PROJECTION_SCHEMA_VERSION,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    authenticate_controller_output,
    build_idempotency_key,
    project_recommendation,
)

import ph_helpers as H


def project(rec):
    """Authenticate through the serialized form, then project."""

    authenticated = authenticate_controller_output(rec.to_canonical_dict())
    return project_recommendation(authenticated)


# --- the ratified identifiers ------------------------------------------------------


def test_projection_carries_the_ratified_d4_identifiers(recommendation):
    projection = project(recommendation)
    request = projection.request
    assert request.requested_purpose == "cloud_scaling.capacity_action"
    assert request.requested_domain == "cloud_scaling"
    assert request.subject_type == "cloud_scaling.capacity_subject"
    assert projection.binding.subject_type == "cloud_scaling.capacity_subject"
    assert request.schema_version == EVALUATION_REQUEST_SCHEMA_VERSION_V2
    assert projection.context.schema_version == SUBJECT_CONTEXT_SCHEMA_VERSION
    assert projection.binding.schema_version == SUBJECT_BINDING_SCHEMA_VERSION
    assert projection.schema_version == PROJECTION_SCHEMA_VERSION


def test_requested_scope_is_minimal_and_never_overloaded(recommendation):
    scope = project(recommendation).request.requested_scope
    assert scope.purposes == (PURPOSE_CAPACITY_ACTION,)
    # No topology, capacity or environment dimension is smuggled into scope.
    assert scope.tools_allow == () and scope.tools_deny == ()
    assert scope.data_allow == () and scope.data_deny == ()
    assert scope.destinations == () and scope.models == () and scope.actors == ()
    assert scope.max_transaction_minor_units is None


def test_risk_class_is_never_asserted_by_the_adapter(recommendation):
    assert project(recommendation).request.requested_risk_class is None


# --- every ActionKind ---------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(ActionKind, key=lambda k: k.value))
def test_every_action_kind_projects_to_its_exact_canonical_value(kind):
    rec = recommendation_for(kind)
    projection = project(rec)
    assert projection.context.action_type == kind.value
    assert projection.context.action_type in CANONICAL_ACTION_TYPES


def test_coordinated_projects_the_primary_change_not_the_dependency():
    rec = recommendation_for(ActionKind.COORDINATED)
    projection = project(rec)
    primary = rec.selected_plan.primary_change
    assert len(rec.selected_plan.changes) >= 2, "the fixture must be genuinely coordinated"
    assert projection.context.magnitude_before == primary.current_capacity
    assert projection.context.magnitude_after == primary.proposed_capacity


def test_no_change_projects_equal_magnitudes():
    projection = project(recommendation_for(ActionKind.NO_CHANGE))
    assert projection.context.magnitude_before == projection.context.magnitude_after


# --- curated neutral facts ----------------------------------------------------------


def test_context_carries_only_curated_neutral_facts(recommendation):
    canonical = project(recommendation).context.to_canonical_dict()
    assert set(canonical) == {
        "schema_version",
        "environment",
        "region",
        "zone",
        "compute_group",
        "resource_class",
        "action_type",
        "magnitude_before",
        "magnitude_after",
        "subject_asserted_at",
        "subject_valid_from",
        "subject_valid_until",
    }
    # Identity and evidence references are authoritative on the OUTER request only.
    for forbidden in ("tenant_id", "subject_id", "evidence_references",
                      "recommendation_digest"):
        assert forbidden not in canonical


def test_no_float_enters_the_risk_authority_digest_chain(recommendation):
    """The controller's float analytics have no path into the RA canonical form."""

    projection = project(recommendation)

    def assert_no_float(value, path="request"):
        if isinstance(value, float):
            raise AssertionError(f"float reached the RA digest chain at {path}")
        if isinstance(value, dict):
            for key, item in value.items():
                assert_no_float(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                assert_no_float(item, f"{path}[{index}]")

    assert_no_float(projection.request.to_canonical_dict())
    # The controller's own serialization *does* carry floats — proving the exclusion is
    # a real filter and not a vacuous assertion over float-free source data.
    controller_form = recommendation.to_canonical_dict()
    assert isinstance(controller_form["expected_forecast_coverage"], float)
    assert isinstance(controller_form["validity_seconds"], float)


def test_analytics_fields_are_absent_from_the_projection(recommendation):
    canonical = project(recommendation).request.to_canonical_dict()
    rendered = repr(canonical)
    for excluded in ("expected_forecast_coverage", "forecast_confidence",
                     "timing_seconds", "estimated_cost_change_minor", "score_breakdown"):
        assert excluded not in rendered


def test_optional_zone_present_and_absent_yield_distinct_digests():
    with_zone = H.subject()
    without_zone = H.subject()
    object.__setattr__(with_zone, "zone", "eu-west-1a")

    zoned = project(build_recommendation(subject=with_zone))
    unzoned = project(build_recommendation(subject=without_zone))

    assert zoned.context.zone == "eu-west-1a"
    assert unzoned.context.zone is None
    assert zoned.context_digest != unzoned.context_digest
    assert zoned.subject_digest != unzoned.subject_digest


def test_missing_optional_is_null_and_never_coerced(recommendation):
    canonical = project(recommendation).context.to_canonical_dict()
    # The controller fixture supplies no environment/region/zone/cluster/resource.
    for name in ("environment", "region", "zone", "compute_group", "resource_class"):
        assert canonical[name] is None, f"{name} must stay the explicit null sentinel"


def test_none_and_empty_string_are_distinct_named_values():
    absent = SubjectContext(
        action_type="scale_up",
        subject_asserted_at=H.at(190.0),
        subject_valid_from=H.at(190.0),
        subject_valid_until=H.at(490.0),
        environment=None,
    )
    named_empty = SubjectContext(
        action_type="scale_up",
        subject_asserted_at=H.at(190.0),
        subject_valid_from=H.at(190.0),
        subject_valid_until=H.at(490.0),
        environment="",
    )
    assert absent.digest() != named_empty.digest()


# --- the binding chain ---------------------------------------------------------------


def test_the_full_binding_chain_reconciles(recommendation):
    projection = project(recommendation)
    assert projection.context.digest() == projection.context_digest
    assert projection.binding.context_digest == projection.context_digest
    assert projection.binding.digest() == projection.subject_digest
    assert projection.request.subject_digest == projection.subject_digest
    assert projection.request.digest() == projection.request_digest


def test_binding_anchors_are_derived_from_the_outer_request(recommendation):
    projection = project(recommendation)
    request, binding = projection.request, projection.binding
    assert binding.tenant_id == request.tenant_id
    assert binding.subject_id == request.subject_id
    assert binding.subject_type == request.subject_type
    assert binding.recommendation_digest == request.recommendation_digest


def test_risk_authority_revalidates_the_binding_independently(recommendation):
    """RA's own Phase 4B validator must reconcile what the adapter produced."""

    projection = project(recommendation)
    validation = validate_subject_binding(projection.request)
    assert validation.context_digest == projection.context_digest
    assert validation.subject_digest == projection.subject_digest
    assert validation.recommendation_digest == projection.recommendation_digest
    assert validation.authority_granted is False
    assert validation.executable is False


def test_reconstructing_the_binding_reproduces_both_digests(recommendation):
    projection = project(recommendation)
    rebuilt_context = SubjectContext.from_dict(projection.context.to_canonical_dict())
    assert rebuilt_context.digest() == projection.context_digest
    rebuilt_binding = SubjectBinding.from_dict(projection.binding.to_canonical_dict())
    assert rebuilt_binding.digest() == projection.subject_digest


def test_request_round_trips_through_from_dict(recommendation):
    projection = project(recommendation)
    rebuilt = SubjectRiskEvaluationRequestV2.from_dict(
        projection.request.to_canonical_dict()
    )
    assert rebuilt.digest() == projection.request_digest
    assert rebuilt.subject_digest == projection.subject_digest
    assert rebuilt.evaluation_time is None


# --- evidence references --------------------------------------------------------------


def test_evidence_references_are_validated_deduplicated_and_ordered(recommendation):
    references = project(recommendation).evidence_references
    assert references == tuple(sorted(set(references)))
    assert all(ref.startswith("sha256:") and len(ref) == 71 for ref in references)
    assert recommendation.forecast_evidence_digest() in references
    assert recommendation.cost_evidence_digest() in references
    assert recommendation.canonical_state_digest() in references


def test_topology_digest_is_carried_only_when_topology_exists(recommendation):
    assert recommendation.topology_digest() is None
    plain = project(recommendation).evidence_references
    assert len(plain) == 3

    coordinated = recommendation_for(ActionKind.COORDINATED)
    assert coordinated.topology_digest() is not None
    assert coordinated.topology_digest() in project(coordinated).evidence_references


def test_evidence_references_carry_no_body_or_control_claim(recommendation):
    for reference in project(recommendation).evidence_references:
        assert isinstance(reference, str)
        assert reference.startswith("sha256:")
        for claim in ("PASS", "FAIL", "ALLOW", "satisfied"):
            assert claim not in reference


# --- idempotency -----------------------------------------------------------------------


def test_idempotency_is_deterministic_across_repeated_projections(recommendation):
    first, second = project(recommendation), project(recommendation)
    assert first.idempotency_key == second.idempotency_key
    assert first.request_digest == second.request_digest


def test_idempotency_matches_the_ratified_d6_formula(recommendation):
    projection = project(recommendation)
    assert projection.idempotency_key == build_idempotency_key(
        tenant_id=projection.tenant_id,
        subject_id=projection.subject_id,
        recommendation_digest=projection.recommendation_digest,
    )


def test_idempotency_reproduces_the_adr_worked_example():
    """Pin the D-6 formula against the digest published in ADR §5.3."""

    assert build_idempotency_key(
        tenant_id="tnt-acme",
        subject_id="wl-checkout-api",
        recommendation_digest="sha256:" + "1" * 64,
    ) == "sha256:42aaa799941a6661c39c3dbe45ea7e7b2ecfcc5d617a9fc09ee32cbbe8959dd0"


def test_idempotency_is_not_a_timestamp_nonce(recommendation):
    """Two recommendations differing only in time must NOT share an idempotency key.

    ...and the key must not vary when nothing but wall-clock time passes. The key is a
    function of identity + recommendation digest + purpose + schema version, never of a
    request timestamp.
    """

    later = build_recommendation(
        recommendation_time=H.at(200.0), recommendation_id="rec-phase4c-1"
    )
    baseline = project(recommendation)
    shifted = project(later)
    # The recommendation digest covers the time, so the key legitimately differs...
    assert baseline.idempotency_key != shifted.idempotency_key
    # ...but re-projecting the SAME recommendation never produces a new key.
    assert project(recommendation).idempotency_key == baseline.idempotency_key


# --- validity window --------------------------------------------------------------------


def test_validity_window_is_projected_from_the_recommendation(recommendation):
    projection = project(recommendation)
    rec_time, validity_seconds = recommendation.validity_interval()
    assert projection.context.subject_asserted_at == rec_time
    assert projection.context.subject_valid_from == rec_time
    assert projection.context.subject_valid_until == rec_time + timedelta(
        seconds=validity_seconds
    )


def test_timestamps_are_canonical_utc(recommendation):
    canonical = project(recommendation).context.to_canonical_dict()
    for name in ("subject_asserted_at", "subject_valid_from", "subject_valid_until"):
        assert canonical[name].endswith("Z")
        assert len(canonical[name]) == len("2026-01-01T00:00:00.000000Z")


# --- the projection grants nothing --------------------------------------------------------


def test_a_projection_grants_no_authority(recommendation):
    projection = project(recommendation)
    for flag in ("policy_resolved", "risk_evaluated", "authority_granted",
                 "envelope_issued", "actiongate_invoked", "credential_issued",
                 "actuation_performed", "effect_verified", "executable"):
        assert getattr(projection, flag) is False


def test_the_request_never_carries_a_caller_evaluation_time(recommendation):
    assert project(recommendation).request.evaluation_time is None
