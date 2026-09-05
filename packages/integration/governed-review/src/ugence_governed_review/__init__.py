"""Ugence Governed Review — binds a human approval to a parked governed proposal.

    THIS PACKAGE BINDS AND CONSUMES AN APPROVAL.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, SIGNALS, RESUMES OR EXECUTES.

Owner rulings HR-1 to HR-5 (``docs/architecture/ADR_UGENCE_HUMAN_REVIEW_DURABLE_RESUME_SCOPING.md``).
This release is HR-A only: the production ``GovernanceInputSource`` that reads the
approval ledger and the authority directory, binds approvals to the proposal
fingerprint, consumes exactly once before the engine advances, and treats only
ESCALATE as reviewable. The review service (HR-C), the studio screens (HR-D) and the
receipt linkage (HR-E) are not here; the bounded adapter resume (HR-B) is a change to
the durable-execution package, not to this one.

Maturity: ``REFERENCE_GRADE_SHADOW_ONLY``. A consumed approval is an input to a
governed composition, not a decision, and nothing downstream of it is weakened.
"""

from __future__ import annotations

from .binding import (
    SUBJECT_KIND,
    ProposalIdentity,
    approval_id_for_identity,
    consumer_ref_for,
    expected_consumption_id,
    identity_of,
    subject_for,
)
from .composition import build_review_ledger, open_directory
from .errors import ClockDisciplineError, ContractViolation, GovernedReviewError
from .source import (
    DEFAULT_REQUEST_VALIDITY,
    REASON_APPROVAL_CONSUMED,
    ApprovalBoundInputSource,
    BindingOutcome,
    BindingState,
)
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # binding (HR-3)
    "SUBJECT_KIND", "ProposalIdentity", "identity_of", "subject_for", "consumer_ref_for",
    "approval_id_for_identity", "expected_consumption_id",
    # the source
    "ApprovalBoundInputSource", "BindingOutcome", "BindingState",
    "REASON_APPROVAL_CONSUMED", "DEFAULT_REQUEST_VALIDITY",
    # composition
    "build_review_ledger", "open_directory",
    # errors
    "GovernedReviewError", "ContractViolation", "ClockDisciplineError",
]
