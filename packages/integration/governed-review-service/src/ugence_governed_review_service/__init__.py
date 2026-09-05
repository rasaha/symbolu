"""Ugence Governed Review Service — lists the review queue, renders a run, and records
a human's decision, then re-arms the instance it binds to.

    THIS SERVICE RECORDS A DECISION A HUMAN ALREADY MADE.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, CLEARS OR EXECUTES.

GAS-7 step HR-C under owner rulings HR-1 to HR-5
(``docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md``). It composes
``ugence_governed_review`` (the binding), the approval ledger, the authority directory's
eligibility adapter and the DBOS adapter; since 0.2.0 it also appends each completed
round trip's receipt linkage to the control-plane audit ledger (HE-1) and exposes it on
run detail (HE-5); since 0.3.0 it defines the service-local ``ApproverIdentityPort``
and the proof shape (AI-A, rulings ID-2 to ID-5), with a fixture adapter only.
Maturity ``REFERENCE_GRADE_SHADOW_ONLY``: the approver on every decision is a presented
reference, not a proven identity, because no real identity adapter exists (AI-C).
"""

from __future__ import annotations

from .errors import ClockDisciplineError, ContractViolation, GovernedReviewServiceError
from .http import ROUTES, build_app, decision_view, queue_entry_view
from .identity import (
    IDENTITY_PROOF_LABELS,
    IDP_AUTHENTICATED,
    PRESENTED_UNPROVEN,
    PROOF_HEADER,
    ActorKind,
    ApproverIdentity,
    ApproverIdentityPort,
    IdentityUnavailable,
    RecordedAssurance,
    StaticApproverIdentityAdapter,
    TenantMode,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
)
from .linkage import (
    LINKAGE_KIND,
    InMemoryLinkageIndex,
    LedgerLinkageIndex,
    LinkageAppender,
    LinkageIndex,
    LinkageOutcome,
    LinkageState,
    linkage_view,
)
from .reader import DbosRunReader, RunReader, StaticRunReader
from .service import (
    SIGNAL_NAME,
    TENANT_SOURCE_CONFIGURED,
    TENANT_SOURCE_PROOF,
    DecisionOutcome,
    DecisionResult,
    QueueEntry,
    ReviewService,
    instance_of,
)
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    IDENTITY_PROOF,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "IDENTITY_PROOF", "ENFORCEMENT_ENABLED",
    "ReviewService", "DecisionOutcome", "DecisionResult", "QueueEntry", "SIGNAL_NAME",
    "TENANT_SOURCE_PROOF", "TENANT_SOURCE_CONFIGURED", "instance_of",
    "ApproverIdentityPort", "ApproverIdentity", "VerifiedClaims", "ActorKind", "TenantMode",
    "RecordedAssurance", "StaticApproverIdentityAdapter", "IdentityUnavailable",
    "PROOF_HEADER", "PRESENTED_UNPROVEN", "IDP_AUTHENTICATED", "IDENTITY_PROOF_LABELS",
    "authentication_reference", "subject_reference",
    "RunReader", "DbosRunReader", "StaticRunReader",
    "ROUTES", "build_app", "queue_entry_view", "decision_view",
    "LINKAGE_KIND", "LinkageAppender", "LinkageIndex", "InMemoryLinkageIndex",
    "LedgerLinkageIndex", "LinkageOutcome", "LinkageState", "linkage_view",
    "GovernedReviewServiceError", "ContractViolation", "ClockDisciplineError",
]
