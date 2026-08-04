"""Three-scope authorization model (PRIVATE_A / PRIVATE_B / SHARED).

This module is a **pure decision function**: it takes explicit facts and returns
a decision. It performs no I/O, so it is exhaustively unit- and property-testable.
Repositories/services supply the facts (ownership, membership status).

Invariants enforced:
- **Default deny.** Any case not explicitly allowed is denied.
- A user may access a PRIVATE resource only if they own it; otherwise the result
  is ``DENY_NOT_FOUND`` so the resource's *existence* is not disclosed (INV-9).
- A SHARED resource requires an **active** couple membership, checked at call time.
- Background-job writes must re-validate membership immediately before writing
  (DEC-027); ``authorize_job_write`` provides that check.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from ..domain.enums import MembershipStatus, Scope
from ..errors import DilChatError, ErrorCode


class Decision(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY_NOT_FOUND = "DENY_NOT_FOUND"      # existence non-disclosure -> 404
    DENY_FORBIDDEN = "DENY_FORBIDDEN"      # existence already known -> 403


@dataclass(frozen=True)
class AuthzResult:
    decision: Decision
    reason_code: str

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW

    def raise_if_denied(self) -> None:
        if self.decision is Decision.ALLOW:
            return
        if self.decision is Decision.DENY_NOT_FOUND:
            raise DilChatError(ErrorCode.NOT_FOUND)
        raise DilChatError(ErrorCode.SCOPE_DENIED, self.reason_code)


@dataclass(frozen=True)
class MembershipFact:
    """What we know about the actor's relationship to a couple."""

    couple_id: uuid.UUID
    status: MembershipStatus | None  # None => actor is not (and was not) a member


def authorize_private(
    actor_user_id: uuid.UUID,
    resource_owner_user_id: uuid.UUID,
) -> AuthzResult:
    """Access to a PRIVATE_A/PRIVATE_B resource. Owner-only; else 404."""
    if actor_user_id == resource_owner_user_id:
        return AuthzResult(Decision.ALLOW, "OWNER")
    # Do NOT reveal that the resource exists.
    return AuthzResult(Decision.DENY_NOT_FOUND, "CROSS_PRIVATE")


def authorize_shared(membership: MembershipFact | None) -> AuthzResult:
    """Access to a SHARED resource requires an active membership."""
    if membership is None or membership.status is None:
        # Actor has no relationship to this couple: do not disclose it exists.
        return AuthzResult(Decision.DENY_NOT_FOUND, "NOT_A_MEMBER")
    if membership.status is MembershipStatus.ACTIVE:
        return AuthzResult(Decision.ALLOW, "ACTIVE_MEMBER")
    # Membership existed but is revoked (e.g. after unpairing): existence is known.
    return AuthzResult(Decision.DENY_FORBIDDEN, "COUPLE_NOT_ACTIVE")


def authorize(
    actor_user_id: uuid.UUID,
    resource_scope: Scope,
    *,
    resource_owner_user_id: uuid.UUID | None = None,
    membership: MembershipFact | None = None,
) -> AuthzResult:
    """Unified default-deny entry point."""
    if resource_scope in (Scope.PRIVATE_A, Scope.PRIVATE_B):
        if resource_owner_user_id is None:
            return AuthzResult(Decision.DENY_NOT_FOUND, "MISSING_OWNER")
        return authorize_private(actor_user_id, resource_owner_user_id)
    if resource_scope is Scope.SHARED:
        return authorize_shared(membership)
    # Unknown scope: default deny.
    return AuthzResult(Decision.DENY_FORBIDDEN, "UNKNOWN_SCOPE")


def authorize_job_write(membership: MembershipFact | None) -> AuthzResult:
    """DEC-027: a background job must re-check membership right before a SHARED write.

    Authorization granted at enqueue time is NOT sufficient; the job calls this
    with the *current* membership fact read inside the write transaction.
    """
    result = authorize_shared(membership)
    if not result.allowed:
        # Distinct reason so the abort is auditable as a job-scope abort.
        return AuthzResult(result.decision, "JOB_WRITE_SCOPE_REVOKED")
    return result
