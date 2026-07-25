"""Procurement composition root — wires the DGM kernel with procurement adapters.

This is the procurement analogue of ``applications.ai_hiring.platform``. It
composes the **unchanged** Decision Governance kernel (``decision_governance``)
with the procurement domain (``domains.procurement``): the governance services,
repositories, audit, identity, and case-validation come straight from the
kernel; procurement supplies the domain adapters that plug into the kernel ports
(linked-record assessment adapter, budget-authority control plane, supplier
execution adapter, access policy).

Kernel concepts are imported directly from ``decision_governance.*``; procurement
concepts from ``domains.procurement.*``. The kernel is treated as a third-party
library — it is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass

from decision_governance.audit import AuditService, InMemoryAuditRepository
from decision_governance.identity import IdentityProvider, StaticIdentityProvider
from decision_governance.repositories import (
    InMemoryActionRequestRepository,
    InMemoryDecisionCaseRepository,
    InMemoryExecutionRepository,
)
from decision_governance.services import (
    ActionAuthorizationService,
    ActionRequestService,
    ActionRequestValidationService,
    CaseDecisionService,
    CaseRecommendationService,
    CaseValidationService,
    CERBindingService,
    CompensationService,
    DecisionCaseService,
    ExecutionService,
    ExecutionValidationService,
    ReconciliationService,
)

from domains.procurement.actions import all_mappings
from domains.procurement.adapters import ProcurementAssessmentLinkedRecordAdapter
from domains.procurement.policies import (
    BudgetAuthorityAdapter,
    InMemoryProcurementAssessmentRepository,
    ProcurementAssessmentService,
    ProcurementPolicyAdapter,
)
from domains.procurement.suppliers import SupplierExecutionAdapter
from domains.procurement.validation import ProcurementRequestValidator

from .configuration import DEFAULT_CONFIGURATION, ProcurementConfiguration

__all__ = ["ProcurementPlatform", "build_in_memory_platform"]


@dataclass
class ProcurementPlatform:
    """A fully-wired procurement platform over the unchanged DGM kernel."""

    configuration: ProcurementConfiguration
    identity_provider: IdentityProvider
    policy_adapter: ProcurementPolicyAdapter
    audit_repo: InMemoryAuditRepository
    audit_service: AuditService
    # --- procurement domain ---
    assessment_repo: InMemoryProcurementAssessmentRepository
    assessment_service: ProcurementAssessmentService
    request_validator: ProcurementRequestValidator
    linked_record_adapter: ProcurementAssessmentLinkedRecordAdapter
    budget_authority: BudgetAuthorityAdapter
    supplier_adapter: SupplierExecutionAdapter
    # --- kernel governance ---
    decision_case_repo: InMemoryDecisionCaseRepository
    action_request_repo: InMemoryActionRequestRepository
    execution_repo: InMemoryExecutionRepository
    case_validation_service: CaseValidationService
    decision_case_service: DecisionCaseService
    case_recommendation_service: CaseRecommendationService
    case_decision_service: CaseDecisionService
    action_request_validation_service: ActionRequestValidationService
    action_request_service: ActionRequestService
    cer_binding_service: CERBindingService
    action_authorization_service: ActionAuthorizationService
    execution_validation_service: ExecutionValidationService
    execution_service: ExecutionService
    reconciliation_service: ReconciliationService
    compensation_service: CompensationService

    def publish_standard_mappings(self, *, actor: str, tenant_id: str) -> None:
        """Publish the standard procurement action mappings (idempotent per test)."""
        for mapping in all_mappings():
            self.action_request_service.publish_action_mapping(
                mapping, actor=actor, tenant_id=tenant_id)

    def build_api(self):
        """Construct the callable procurement API facade."""
        from .api.routes import ProcurementAPI

        return ProcurementAPI(self)


def build_in_memory_platform(
    configuration: ProcurementConfiguration | None = None,
    identity_provider: IdentityProvider | None = None,
) -> ProcurementPlatform:
    """Wire an in-memory procurement platform on the unchanged DGM kernel."""
    config = configuration or DEFAULT_CONFIGURATION
    identity = identity_provider or StaticIdentityProvider()

    policy_adapter = ProcurementPolicyAdapter()
    policy = policy_adapter.policy
    audit_repo = InMemoryAuditRepository()
    audit_service = AuditService(audit_repo)

    # --- procurement domain services & adapters ---
    assessment_repo = InMemoryProcurementAssessmentRepository()
    assessment_service = ProcurementAssessmentService(assessment_repo)
    request_validator = ProcurementRequestValidator(
        known_suppliers=config.known_suppliers, known_budgets=config.known_budgets)
    linked_record_adapter = ProcurementAssessmentLinkedRecordAdapter(assessment_repo)
    budget_authority = BudgetAuthorityAdapter(
        hard_limit=config.hard_limit, approval_threshold=config.approval_threshold,
        restricted_suppliers=config.restricted_suppliers,
        restricted_budgets=config.restricted_budgets)
    supplier_adapter = SupplierExecutionAdapter(
        transport_failing=config.supplier_transport_failing,
        timing_out=config.supplier_timing_out)

    # --- kernel governance (unchanged) ---
    decision_case_repo = InMemoryDecisionCaseRepository()
    action_request_repo = InMemoryActionRequestRepository()
    execution_repo = InMemoryExecutionRepository()

    case_validation_service = CaseValidationService(linked_record_adapter)
    decision_case_service = DecisionCaseService(
        decision_case_repo, case_validation_service, audit_service, identity, policy)
    case_recommendation_service = CaseRecommendationService(
        decision_case_repo, case_validation_service, audit_service, identity, policy)
    case_decision_service = CaseDecisionService(
        decision_case_repo, case_validation_service, audit_service, identity, policy)
    action_request_validation_service = ActionRequestValidationService(
        action_request_repo, decision_case_repo)
    action_request_service = ActionRequestService(
        action_request_repo, decision_case_repo, action_request_validation_service,
        audit_service, identity, policy)
    cer_binding_service = CERBindingService(
        action_request_repo, decision_case_repo, audit_service, identity, policy)
    action_authorization_service = ActionAuthorizationService(
        action_request_repo, budget_authority, audit_service, identity, policy)
    execution_validation_service = ExecutionValidationService(
        execution_repo, action_request_repo)
    execution_service = ExecutionService(
        execution_repo, action_request_repo, execution_validation_service,
        supplier_adapter, audit_service, identity, policy)
    reconciliation_service = ReconciliationService(
        execution_repo, supplier_adapter, audit_service, identity, policy)
    compensation_service = CompensationService(
        execution_repo, audit_service, identity, policy)

    return ProcurementPlatform(
        configuration=config,
        identity_provider=identity,
        policy_adapter=policy_adapter,
        audit_repo=audit_repo,
        audit_service=audit_service,
        assessment_repo=assessment_repo,
        assessment_service=assessment_service,
        request_validator=request_validator,
        linked_record_adapter=linked_record_adapter,
        budget_authority=budget_authority,
        supplier_adapter=supplier_adapter,
        decision_case_repo=decision_case_repo,
        action_request_repo=action_request_repo,
        execution_repo=execution_repo,
        case_validation_service=case_validation_service,
        decision_case_service=decision_case_service,
        case_recommendation_service=case_recommendation_service,
        case_decision_service=case_decision_service,
        action_request_validation_service=action_request_validation_service,
        action_request_service=action_request_service,
        cer_binding_service=cer_binding_service,
        action_authorization_service=action_authorization_service,
        execution_validation_service=execution_validation_service,
        execution_service=execution_service,
        reconciliation_service=reconciliation_service,
        compensation_service=compensation_service,
    )
