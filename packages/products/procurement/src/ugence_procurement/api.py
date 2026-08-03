"""Ugence Procurement — curated public API.

    import ugence_procurement.api

This is the single stable, supported product surface. It re-exports the
product-level contracts and entry points from their canonical implementation
modules (object identity preserved — the names here *are* the canonical objects).
Internal repositories, helpers, and kernel plumbing are deliberately **not**
exported here even though they exist; import those from their modules directly if
you must, with no stability guarantee.

The exact set of names below is frozen against ``artifacts/public_api.json`` and
enforced by a test — adding or removing a public name is a deliberate, reviewed
API change.
"""

from __future__ import annotations

# --- request & item contracts -------------------------------------------------
from .requests.contracts import (
    BudgetReference,
    PurchaseItem,
    PurchaseRequest,
    RequestStatus,
    SupplierReference,
    Urgency,
)

# --- deterministic request validation -----------------------------------------
from .validation.request_validation import ProcurementRequestValidator

# --- deterministic policy assessment ------------------------------------------
from .policies.assessment import (
    AssessmentStatus,
    InMemoryProcurementAssessmentRepository,
    PolicyAssessment,
    PolicyCheck,
    ProcurementAssessmentService,
)
from .policies.budget_authority import BudgetAuthorityAdapter
from .policies.policy_adapter import ProcurementPolicyAdapter

# --- advisory recommendation & binding approval vocabulary --------------------
from .approvals.mappings import (
    APPROVAL_TO_DECISION,
    RECOMMENDATION_TO_PROPOSED,
    PurchaseApproval,
    PurchaseRecommendation,
    decision_outcome_for,
    proposed_outcome_for,
)

# --- decision → governed action mappings --------------------------------------
from .actions.mappings import (
    CANCEL_REQUEST,
    CREATE_PURCHASE_ORDER,
    PROCUREMENT_DECISION_TYPE,
    REQUEST_MORE_INFORMATION,
    ROUTE_TO_SENIOR_APPROVER,
    SUPPLIER_SYSTEM_TYPE,
    all_mappings,
)

# --- supplier execution adapter & outcome vocabulary --------------------------
from .suppliers.adapter import SupplierExecutionAdapter
from .suppliers.outcomes import (
    SUPPLIER_TO_BUSINESS,
    SupplierOutcome,
    business_outcome_for,
)

# --- linked-record adapter (assessment → neutral kernel snapshot) -------------
from .adapters.linked_records import ProcurementAssessmentLinkedRecordAdapter

# --- procurement error taxonomy & stable reason codes -------------------------
from .errors import (
    AssessmentNotFinalizedError,
    BudgetNotKnownError,
    DomainValidationError,
    ProcurementError,
    PurchaseRequestValidationError,
    SupplierNotKnownError,
)

# --- configuration + composition root + callable facade -----------------------
from .configuration import DEFAULT_CONFIGURATION, ProcurementConfiguration
from .platform import ProcurementPlatform, build_in_memory_platform
from .routes import ProcurementAPI, ProcurementRunResult

# --- version + maturity metadata ----------------------------------------------
from .version import VersionInfo, version_info
from .product.version import ProductMaturity, product_maturity

__all__ = [
    # requests
    "PurchaseRequest",
    "PurchaseItem",
    "SupplierReference",
    "BudgetReference",
    "Urgency",
    "RequestStatus",
    # validation
    "ProcurementRequestValidator",
    # assessment
    "PolicyAssessment",
    "PolicyCheck",
    "AssessmentStatus",
    "ProcurementAssessmentService",
    "InMemoryProcurementAssessmentRepository",
    "BudgetAuthorityAdapter",
    "ProcurementPolicyAdapter",
    # approvals / recommendations
    "PurchaseRecommendation",
    "PurchaseApproval",
    "RECOMMENDATION_TO_PROPOSED",
    "APPROVAL_TO_DECISION",
    "proposed_outcome_for",
    "decision_outcome_for",
    # actions
    "PROCUREMENT_DECISION_TYPE",
    "SUPPLIER_SYSTEM_TYPE",
    "CREATE_PURCHASE_ORDER",
    "CANCEL_REQUEST",
    "ROUTE_TO_SENIOR_APPROVER",
    "REQUEST_MORE_INFORMATION",
    "all_mappings",
    # suppliers
    "SupplierExecutionAdapter",
    "SupplierOutcome",
    "SUPPLIER_TO_BUSINESS",
    "business_outcome_for",
    # adapters
    "ProcurementAssessmentLinkedRecordAdapter",
    # errors
    "ProcurementError",
    "DomainValidationError",
    "PurchaseRequestValidationError",
    "AssessmentNotFinalizedError",
    "SupplierNotKnownError",
    "BudgetNotKnownError",
    # configuration + platform + facade
    "ProcurementConfiguration",
    "DEFAULT_CONFIGURATION",
    "ProcurementPlatform",
    "build_in_memory_platform",
    "ProcurementAPI",
    "ProcurementRunResult",
    # version + maturity
    "version_info",
    "VersionInfo",
    "product_maturity",
    "ProductMaturity",
]
