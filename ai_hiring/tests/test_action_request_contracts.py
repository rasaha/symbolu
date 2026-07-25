"""Phase 4B contract invariants: immutable requests, mappings, CERs, responses."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_hiring.action_requests import (
    ActionAuthorizationResponse,
    ActionMapping,
    ActionMappingStatus,
    ActionRequest,
    ActionRequestStatus,
    AuthorizationOutcome,
    ContextEnvelopeRecord,
    ParameterSchema,
)
from ai_hiring.decision_cases import DecisionOutcome, SubjectRef, VersionedRef
from ai_hiring.errors import (
    ActionMappingNotPublishedError,
    ActionParameterValidationError,
    DecisionNotActionableError,
    DomainValidationError,
    ProhibitedActionParameterError,
    TargetSystemNotPermittedError,
)

from .conftest import (
    MAPPING_ADMIN,
    OPS,
    TENANT,
    action_platform,  # noqa: F401 (fixture)
    decided_case,
    make_action_mapping,
    published_mapping,
)

INVALID = (ValidationError, DomainValidationError)


def _request(**kw) -> ActionRequest:
    base = dict(action_request_id="ar1", tenant_id="t1", decision_case_id="dc1",
                decision_case_version=1, decision_id="d1", action_type="ADVANCE",
                target_system="ATS", subject_refs=(SubjectRef(subject_id="c1"),),
                action_mapping_ref=VersionedRef(ref_id="m1", version=1),
                created_by="ops-1", request_version_id="rv1")
    base.update(kw)
    return ActionRequest(**base)


def test_action_request_is_frozen_and_has_no_execution_state():
    req = _request()
    with pytest.raises(ValidationError):
        req.status = ActionRequestStatus.AUTHORIZED
    forbidden = {"execution", "executed", "execution_result", "execution_record",
                 "succeeded", "result"}
    assert forbidden.isdisjoint(ActionRequest.model_fields.keys())


def test_no_executed_or_succeeded_status_exists():
    names = {s.value for s in ActionRequestStatus}
    assert "EXECUTED" not in names and "SUCCEEDED" not in names


def test_action_request_evolve_is_append_only():
    req = _request()
    evolved = req.evolve(request_version_id="rv2", status=ActionRequestStatus.CANCELLED)
    assert evolved.version == 2 and req.version == 1
    assert evolved.status is ActionRequestStatus.CANCELLED
    assert req.status is ActionRequestStatus.DRAFT


def test_cer_is_frozen_and_hash_is_stable():
    cer = _make_cer()
    with pytest.raises(ValidationError):
        cer.action_type = "SOMETHING"
    assert cer.compute_hash() == cer.compute_hash()


def test_cer_changed_material_input_changes_hash():
    cer = _make_cer()
    other = cer.model_copy(update={"action_type": "CLOSE_CANDIDATE_WORKFLOW"})
    assert cer.compute_hash() != other.compute_hash()


def test_authorization_response_is_frozen_and_constraints_required():
    resp = ActionAuthorizationResponse(
        authorization_id="az1", action_request_id="ar1", cer_id="cer1",
        outcome=AuthorizationOutcome.AUTHORIZED)
    with pytest.raises(ValidationError):
        resp.outcome = AuthorizationOutcome.DENIED
    with pytest.raises(INVALID):  # constrained must carry a constraint
        ActionAuthorizationResponse(
            authorization_id="az2", action_request_id="ar1", cer_id="cer1",
            outcome=AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS, constraints=())


def test_mapping_rejects_credential_like_fields():
    with pytest.raises(INVALID):
        ParameterSchema(required_fields=("api_key",))


def test_mapping_hash_is_deterministic():
    m = make_action_mapping()
    assert m.compute_hash() == m.compute_hash()


# --- service-level contract enforcement ---------------------------------

def test_unpublished_mapping_is_rejected(action_platform):
    _, decision = decided_case(action_platform)
    # Save a DRAFT (unpublished) mapping directly into the repo.
    draft = make_action_mapping()
    action_platform.action_request_repo.save_action_mapping(draft)
    with pytest.raises(ActionMappingNotPublishedError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_unsupported_outcome_fails_closed(action_platform):
    """A REJECT decision with only an ADVANCE mapping is not action-producing."""
    _, decision = decided_case(action_platform, outcome=DecisionOutcome.REJECT)
    published_mapping(action_platform)  # ADVANCE mapping only
    with pytest.raises(DecisionNotActionableError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_invalid_target_system_is_rejected(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    with pytest.raises(TargetSystemNotPermittedError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="SOME_OTHER_SYSTEM", created_by=OPS,
            requested_parameters={"stage": "x"})


def test_prohibited_parameter_is_rejected(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    with pytest.raises(ProhibitedActionParameterError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS,
            requested_parameters={"stage": "x", "salary": "100000"})


def test_schema_violation_missing_required_is_rejected(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    with pytest.raises(ActionParameterValidationError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS,
            requested_parameters={"note": "no stage provided"})


def test_exact_mapping_version_is_pinned(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform, version=1)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"})
    assert req.action_mapping_ref.ref_id == "map.advance"
    assert req.action_mapping_ref.version == 1


def _make_cer() -> ContextEnvelopeRecord:
    from ai_hiring.action_requests import (
        AuthoritySummary, DecisionContext, PolicyContext, SubjectContext)
    from ai_hiring.decision_cases import AuthorityType
    return ContextEnvelopeRecord(
        cer_id="cer1", tenant_id="t1", decision_case_id="dc1", decision_id="d1",
        action_request_id="ar1", action_type="ADVANCE_WORKFLOW_STAGE",
        target_system="ATS",
        subject_context=SubjectContext(subject_refs=(SubjectRef(subject_id="c1"),)),
        authority_context=AuthoritySummary(authority_type=AuthorityType.HUMAN_APPROVER),
        policy_context=PolicyContext(),
        decision_context=DecisionContext(
            decision_case_id="dc1", decision_case_version=1, decision_id="d1",
            decision_outcome=DecisionOutcome.ADVANCE))
