"""Happy-path conformance for the v2 neutral subject-context contract layer (Phase 4A).

Covers: complete and sparse ``SubjectContext`` construction, deterministic
schema-tagged digests (pinned against the merged ADR §5.3 worked example),
direct-construction / ``from_dict`` parity, v2 round trips, the pure binding
validator, and proof that frozen v1 behavior is untouched.

The adversarial counterpart is
``tests/adversarial/test_subject_binding_adversarial.py``.
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
    SubjectBindingValidation,
    SubjectContext,
    SubjectRiskEvaluationRequest,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)

# --- ADR §5.3 worked-example fixtures (reproducible byte-for-byte) -------------------
T0 = datetime(2026, 8, 13, 4, 0, 0, tzinfo=timezone.utc)
ADR_CONTEXT_DIGEST = "sha256:9af3f626a08e888a2916215a59c965e221179388ba3987cbbc6b2e0e64cfdbb0"
ADR_SUBJECT_DIGEST = "sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38"
REC_DIGEST = "sha256:" + "1" * 64

# The frozen v1 identity this PR must not perturb.
FROZEN_V1_DIGEST = "sha256:88e9e559e860a637aa0a4389d2f0bc4597767b052dbe9b23a24d30dd09869809"

# The frozen canonical identity of `risk-subject-evaluation-request-2`, computed with the
# existing RA canonicalizer over the fixture built by `v2_request()` below, and carried as
# the corrected ADR §5.3 worked request digest (it supersedes the obsolete
# `sha256:b1973925…`, which predates the outer `recommendation_digest` field).
# Any field added, removed, renamed or re-serialized on v2 changes this value and fails
# `test_v2_request_frozen_digest_fixture` — that is exactly its purpose.
FROZEN_V2_REQUEST_DIGEST = "sha256:cd6dc88a3123959da32df7e03e936867416120099bdd303ebc954c6f04bdbcfb"

# The ADR §5.3 worked request digest as corrected by Amendment 1 (same illustrative values
# as the ADR, in the complete implemented v2 shape). Supersedes `sha256:b1973925…`.
ADR_CORRECTED_REQUEST_DIGEST = "sha256:ac0bdada8d0c93cff831503772f1e3a0a75cc82ab3c41440407a0185443d5ece"


def adr_context() -> SubjectContext:
    """The exact ``SubjectContext`` the merged ADR §5.3 worked example describes."""

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


def adr_binding(context_digest: str = ADR_CONTEXT_DIGEST) -> SubjectBinding:
    return SubjectBinding(
        tenant_id="tnt-acme",
        subject_id="wl-checkout-api",
        subject_type="cloud_scaling.capacity_action",
        recommendation_digest=REC_DIGEST,
        context_digest=context_digest,
    )


def v2_request(**overrides) -> SubjectRiskEvaluationRequestV2:
    context = overrides.pop("subject_context", adr_context())
    base = dict(
        subject_type="cloud_scaling.capacity_action",
        subject_id="wl-checkout-api",
        subject_digest=ADR_SUBJECT_DIGEST,
        tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action",
        requested_domain="cloud_scaling",
        requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
        evidence_references=("sha256:aaa", "sha256:bbb"),
        correlation_id="corr-42",
        subject_context=context,
        recommendation_digest=REC_DIGEST,
    )
    base.update(overrides)
    return SubjectRiskEvaluationRequestV2(**base)


def v1_request() -> SubjectRiskEvaluationRequest:
    return SubjectRiskEvaluationRequest(
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


# --- schema tags --------------------------------------------------------------------


def test_schema_tags_are_the_adr_identifiers():
    assert SUBJECT_CONTEXT_SCHEMA_VERSION == "risk-subject-context-1"
    assert SUBJECT_BINDING_SCHEMA_VERSION == "risk-subject-binding-1"
    assert EVALUATION_REQUEST_SCHEMA_VERSION_V2 == "risk-subject-evaluation-request-2"


# --- SubjectContext -----------------------------------------------------------------


def test_complete_context_reproduces_the_adr_worked_example_digest():
    context = adr_context()
    assert context.schema_version == SUBJECT_CONTEXT_SCHEMA_VERSION
    assert context.digest() == ADR_CONTEXT_DIGEST


def test_context_canonical_form_matches_the_adr_field_set():
    assert set(adr_context().to_canonical_dict()) == {
        "schema_version", "environment", "region", "zone", "compute_group",
        "resource_class", "action_type", "magnitude_before", "magnitude_after",
        "subject_asserted_at", "subject_valid_from", "subject_valid_until",
    }


def test_context_with_every_optional_missing_is_valid_and_deterministic():
    sparse = SubjectContext(
        action_type="no_change",
        subject_asserted_at=T0,
        subject_valid_from=T0,
        subject_valid_until=T0,
    )
    canonical = sparse.to_canonical_dict()
    # Optionals are the explicit null sentinel, never omitted from the canonical form.
    for name in ("environment", "region", "zone", "compute_group", "resource_class",
                 "magnitude_before", "magnitude_after"):
        assert name in canonical and canonical[name] is None
    assert sparse.digest() == sparse.digest()
    assert SubjectContext.from_dict(canonical) == sparse


def test_context_direct_construction_and_from_dict_parity():
    context = adr_context()
    rebuilt = SubjectContext.from_dict(context.to_canonical_dict())
    assert rebuilt == context
    assert rebuilt.digest() == context.digest()


def test_context_round_trip_is_digest_stable_across_repeats():
    context = adr_context()
    for _ in range(3):
        context = SubjectContext.from_dict(context.to_canonical_dict())
    assert context.digest() == ADR_CONTEXT_DIGEST


def test_context_accepts_equal_validity_bounds():
    instant = SubjectContext(
        action_type="scale_down",
        subject_asserted_at=T0,
        subject_valid_from=T0,
        subject_valid_until=T0,
    )
    assert instant.digest().startswith("sha256:")


# --- SubjectBinding -----------------------------------------------------------------


def test_binding_reproduces_the_adr_worked_example_subject_digest():
    assert adr_binding().digest() == ADR_SUBJECT_DIGEST


def test_binding_direct_construction_and_from_dict_parity():
    binding = adr_binding()
    rebuilt = SubjectBinding.from_dict(binding.to_canonical_dict())
    assert rebuilt == binding
    assert rebuilt.digest() == binding.digest()


def test_binding_canonical_form_carries_only_binding_anchors():
    assert set(adr_binding().to_canonical_dict()) == {
        "schema_version", "tenant_id", "subject_id", "subject_type",
        "recommendation_digest", "context_digest",
    }


# --- v2 request ---------------------------------------------------------------------


def test_v2_request_round_trip_is_digest_stable():
    request = v2_request()
    rebuilt = SubjectRiskEvaluationRequestV2.from_dict(request.to_canonical_dict())
    assert rebuilt == request
    assert rebuilt.digest() == request.digest()
    assert rebuilt.subject_context == adr_context()


def test_v2_request_carries_the_raw_inspectable_context_and_recommendation_digest():
    canonical = v2_request().to_canonical_dict()
    assert canonical["subject_context"] == adr_context().to_canonical_dict()
    assert canonical["recommendation_digest"] == REC_DIGEST
    assert canonical["schema_version"] == EVALUATION_REQUEST_SCHEMA_VERSION_V2


def test_v2_request_without_a_context_is_v1_shaped_and_valid():
    bare = SubjectRiskEvaluationRequestV2(
        subject_type="x",
        subject_id="s",
        subject_digest="sha256:" + "0" * 64,
        tenant_id="t",
        requested_purpose="p",
        requested_domain="d",
        requested_scope=Scope(purposes=("p",)),
    )
    canonical = bare.to_canonical_dict()
    assert canonical["subject_context"] is None
    assert canonical["recommendation_digest"] is None
    assert SubjectRiskEvaluationRequestV2.from_dict(canonical) == bare


def test_v2_request_digest_is_deterministic_across_independent_construction():
    assert v2_request().digest() == v2_request().digest()


def test_v2_request_frozen_digest_fixture():
    """Freeze the canonical identity of `risk-subject-evaluation-request-2`.

    Direct construction, canonical serialization and `digest()` are all pinned, so an
    accidental schema change to v2 cannot pass unnoticed the way it could when the only
    assertions were self-referential."""

    assert v2_request().digest() == FROZEN_V2_REQUEST_DIGEST


def test_v2_request_frozen_digest_survives_a_from_dict_round_trip():
    rebuilt = SubjectRiskEvaluationRequestV2.from_dict(v2_request().to_canonical_dict())
    assert rebuilt.digest() == FROZEN_V2_REQUEST_DIGEST


def test_v2_request_frozen_canonical_field_set():
    # The exact serialized key set the frozen digest is computed over.
    assert set(v2_request().to_canonical_dict()) == {
        "schema_version", "subject_type", "subject_id", "subject_digest", "tenant_id",
        "requested_purpose", "requested_domain", "requested_scope", "requested_risk_class",
        "jurisdictions", "requested_tools", "requested_autonomy_level",
        "requested_data_classes", "evidence_references", "correlation_id",
        "idempotency_key", "evaluation_time", "subject_context", "recommendation_digest",
    }


def test_corrected_adr_worked_request_digest_reproduces():
    """The ADR §5.3 worked request, as corrected by Amendment 1.

    Same illustrative values as the ADR (four evidence references, the D-6 idempotency
    key), now in the complete implemented v2 shape including the outer
    `recommendation_digest`. This pins the ADR's own reference example against the
    implementation, so the two cannot drift apart silently."""

    adr_worked = SubjectRiskEvaluationRequestV2(
        subject_type="cloud_scaling.capacity_action",
        subject_id="wl-checkout-api",
        subject_digest=ADR_SUBJECT_DIGEST,
        tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action",
        requested_domain="cloud_scaling",
        requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
        evidence_references=("sha256:aaa", "sha256:bbb", "sha256:ccc", "sha256:ddd"),
        correlation_id="corr-42",
        idempotency_key="sha256:42aaa799941a6661c39c3dbe45ea7e7b2ecfcc5d617a9fc09ee32cbbe8959dd0",
        subject_context=adr_context(),
        recommendation_digest=REC_DIGEST,
    )
    assert adr_worked.digest() == ADR_CORRECTED_REQUEST_DIGEST
    # It reconciles, and the obsolete pre-amendment digest is not reproducible.
    assert validate_subject_binding(adr_worked).subject_digest == ADR_SUBJECT_DIGEST
    assert adr_worked.digest() != "sha256:b1973925e2cb80dcd69e993a1cc8d9f2743cb3b4e799f6772e88909ddd77bd0a"


def test_v2_frozen_digest_is_computed_by_the_real_canonicalizer():
    from risk_authority.crypto.canonical import canonical_bytes
    from risk_authority.crypto.hashing import digest as ra_digest

    assert ra_digest(v2_request().to_canonical_dict()) == FROZEN_V2_REQUEST_DIGEST
    assert canonical_bytes(v2_request().to_canonical_dict()).startswith(b'{"correlation_id"')


# --- pure binding validator ---------------------------------------------------------


def test_validate_subject_binding_returns_a_typed_result_over_the_adr_example():
    result = validate_subject_binding(v2_request())
    assert isinstance(result, SubjectBindingValidation)
    assert result.context_digest == ADR_CONTEXT_DIGEST
    assert result.subject_digest == ADR_SUBJECT_DIGEST
    assert result.tenant_id == "tnt-acme"
    assert result.subject_id == "wl-checkout-api"
    assert result.subject_type == "cloud_scaling.capacity_action"
    assert result.recommendation_digest == REC_DIGEST
    assert result.binding == adr_binding()


def test_validate_subject_binding_is_deterministic_and_pure():
    request = v2_request()
    first, second = validate_subject_binding(request), validate_subject_binding(request)
    assert first == second


def test_validator_reconstructs_the_binding_from_outer_fields_only():
    # The returned binding's identity comes from the OUTER request, and the context
    # itself carries no identity copy that could disagree.
    result = validate_subject_binding(v2_request())
    assert result.binding.tenant_id == "tnt-acme"
    assert result.binding.subject_id == "wl-checkout-api"
    assert "tenant_id" not in adr_context().to_canonical_dict()
    assert "subject_id" not in adr_context().to_canonical_dict()


# --- v1 preservation ----------------------------------------------------------------


def test_v1_digest_fixture_is_unchanged():
    assert v1_request().digest() == FROZEN_V1_DIGEST


def test_v1_serialization_gains_no_v2_fields():
    canonical = v1_request().to_canonical_dict()
    assert "subject_context" not in canonical
    assert "recommendation_digest" not in canonical
    assert canonical["schema_version"] == EVALUATION_REQUEST_SCHEMA_VERSION


def test_v1_round_trip_is_unchanged():
    request = v1_request()
    rebuilt = SubjectRiskEvaluationRequest.from_dict(request.to_canonical_dict())
    assert rebuilt == request
    assert rebuilt.digest() == FROZEN_V1_DIGEST


def test_seam_supported_request_schema_set_is_unchanged_by_phase_4a():
    # Phase 4A ships contracts + pure validation only; wiring is Phase 4B.
    assert SUPPORTED_REQUEST_SCHEMA_VERSIONS == frozenset({EVALUATION_REQUEST_SCHEMA_VERSION})
