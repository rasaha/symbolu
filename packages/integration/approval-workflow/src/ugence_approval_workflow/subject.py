"""The neutral subject an approval binds to.

Ratified decision D-3: the workflow's artifact binds to
``(tenant_id, subject_kind, subject_digest)`` — never to a policy pack id. The
Policy Workflow Compiler's ``HumanApprovalRecord`` keeps its pack-bound meaning
and is neither imported nor amended
(``packages/tooling/policy-workflow-compiler/.../models/approvals.py:31``).

``subject_kind`` is a free label (``policy_pack``, ``decision_case``,
``scaling_recommendation``, …) recorded for readability and never interpreted, in
the same spirit as Decision Authority's ``VersionedRef.kind``. ``subject_digest``
is the caller's content digest of the thing being approved: approval binds to
substance, so a changed subject yields a different digest and can never inherit a
standing decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._canon import domain_digest, optional_text, require_nonempty
from .errors import ContractViolation

__all__ = ["ApprovalSubject", "APPROVAL_ID_PREFIX", "approval_id_for"]

APPROVAL_ID_PREFIX = "apr_"


@dataclass(frozen=True)
class ApprovalSubject:
    """What is being approved, as an opaque, tenant-scoped content identity."""

    tenant_id: str
    subject_kind: str
    subject_digest: str
    subject_ref: str = ""

    def __post_init__(self) -> None:
        for name in ("tenant_id", "subject_kind", "subject_digest"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), f"ApprovalSubject.{name}"))
        object.__setattr__(self, "subject_ref", optional_text(self.subject_ref, "ApprovalSubject.subject_ref"))

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.tenant_id, self.subject_kind, self.subject_digest)

    def canonical_digest(self) -> str:
        return domain_digest("subject", {
            "tenant_id": self.tenant_id,
            "subject_kind": self.subject_kind,
            "subject_digest": self.subject_digest,
        })


def approval_id_for(subject: ApprovalSubject, requested_by: str, request_ordinal: int) -> str:
    """Deterministic approval id: no UUID, no clock.

    ``request_ordinal`` is how a caller raises a genuinely new request for the same
    subject and requester (for instance after a withdrawal). A superseding request
    after ``CHANGES_REQUIRED`` carries a *different* subject digest and therefore a
    different id by construction.
    """

    if not isinstance(request_ordinal, int) or isinstance(request_ordinal, bool) or request_ordinal < 1:
        raise ContractViolation("request_ordinal must be an integer >= 1")
    return APPROVAL_ID_PREFIX + domain_digest("approval_id", {
        "subject": subject.canonical_digest(),
        "requested_by": require_nonempty(requested_by, "requested_by"),
        "request_ordinal": request_ordinal,
    })[:32]

