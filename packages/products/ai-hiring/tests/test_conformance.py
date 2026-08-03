"""Run the reusable kernel conformance kit against the AI Hiring domain.

Proves the *same* domain-agnostic conformance battery that validates Procurement
validates AI Hiring unchanged — both drive the identical kernel governance chain.
"""

from __future__ import annotations

from ugence_decision_authority.api.repositories import (
    InMemoryActionRequestRepository,
    InMemoryDecisionCaseRepository,
    InMemoryExecutionRepository,
)
from ugence_decision_authority.api.services import (
    ActionAuthorizationService,
    ActionRequestService,
    CaseDecisionService,
    DecisionCaseService,
    ExecutionService,
    ReconciliationService,
)
from ugence_decision_authority.conformance import (
    LifecycleOutcome,
    SimpleFixture,
    run_domain_conformance,
)
from ugence_decision_authority.policy import AccessGrant, Permission
from ugence_decision_authority.identity import StaticIdentityProvider

from ugence_ai_hiring import build_in_memory_platform

from .conftest import (
    ASSESSOR,
    DECISION_MAKER,
    EXECUTOR,
    MAPPING_ADMIN,
    OPS,
    RECONCILER,
    TENANT,
    decided_case,
    published_mapping,
)

_SERVICE_TYPES = {
    "decision_case_service": DecisionCaseService,
    "case_decision_service": CaseDecisionService,
    "action_request_service": ActionRequestService,
    "action_authorization_service": ActionAuthorizationService,
    "execution_service": ExecutionService,
    "reconciliation_service": ReconciliationService,
}
_REPO_TYPES = {
    "decision_case_repo": InMemoryDecisionCaseRepository,
    "action_request_repo": InMemoryActionRequestRepository,
    "execution_repo": InMemoryExecutionRepository,
}
_GRANTED = (ASSESSOR, DECISION_MAKER, OPS, MAPPING_ADMIN, EXECUTOR, RECONCILER)


def _build_platform():
    idp = StaticIdentityProvider()
    for actor in _GRANTED:
        idp.register_human(actor)
    platform = build_in_memory_platform(idp)
    for actor in _GRANTED:
        platform.access_grants.add(AccessGrant(actor, TENANT, frozenset(Permission)))
    return platform


def _run_lifecycle(platform) -> LifecycleOutcome:
    _, decision = decided_case(platform)
    published_mapping(platform)
    req = platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"})
    platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    platform.cer_binding_service.bind_cer(request_id=req.action_request_id, actor=OPS)
    platform.action_authorization_service.submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    intent = platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    recon = platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    return LifecycleOutcome(
        audit_events=tuple(platform.audit_service._repo.all()),
        reconciliation_status=recon.status.value,
        records=(decision, req, recon),
        audit_repository=platform.audit_service._repo)


def hiring_fixture() -> SimpleFixture:
    return SimpleFixture(
        name="hiring", _build=_build_platform, _run=_run_lifecycle,
        _service_types=_SERVICE_TYPES, _repo_types=_REPO_TYPES)


def test_hiring_passes_kernel_conformance():
    report = run_domain_conformance(hiring_fixture())
    assert report.passed, report.failures
    assert len(report.results) >= 15
