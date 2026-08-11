"""Driven post-issuance case-state transitions (RA-6 §11, §14).

The states and events already exist in the leaf but nothing drives them in
production (RA-6 §0.2). This module supplies the ratified drivers of
``ACTIVE → {EXPIRED, REVOKED, SUPERSEDED}`` using the leaf's guarded
``RiskDecisionCase.transition`` and the **existing** event types — no new event
type is introduced (RA-6 §11).

Key safety properties preserved:

* No reactivation from a terminal authority state — the leaf state machine has no
  successor for ``REVOKED`` / ``EXPIRED`` / ``SUPERSEDED`` (invariant I4), so an
  attempt raises ``IllegalTransitionError`` here rather than resurrecting
  authority. A new grant requires a **new envelope** (a new case), never a
  revival (invariant I5).
* Expiration stays distinct from revocation (RA-6 §14): the cryptographic
  verifier is authoritative for expiry; this transition is only the *audit
  reflection* when a reaper observes ``now > expires_at``. It writes no
  revocation record.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from risk_authority.domain.enums import GovernanceEventType, RiskCaseState
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from risk_authority.domain.errors import IllegalTransitionError
from risk_authority.domain.events import GovernanceEvent
from risk_authority.domain.risk_case import RiskDecisionCase
from risk_authority.services.revocation import RevocationState

__all__ = [
    "expire_case_if_elapsed",
    "revoke_case",
    "supersede_case",
    "reconcile_case_state",
]


def expire_case_if_elapsed(
    case: RiskDecisionCase,
    *,
    expires_at: datetime,
    now: datetime,
    actor: str = "lifecycle-reaper",
) -> Optional[GovernanceEvent]:
    """Transition an ACTIVE case to EXPIRED when ``now > expires_at`` (audit only)."""

    if case.state is not RiskCaseState.ACTIVE or now <= expires_at:
        return None
    return case.transition(
        target=RiskCaseState.EXPIRED,
        actor=actor,
        reason=f"envelope expired at {expires_at.isoformat()}",
        now=now,
        event_type=GovernanceEventType.CASE_STATE_CHANGED,
    )


def revoke_case(
    case: RiskDecisionCase,
    *,
    now: datetime,
    reason: str,
    actor: str,
) -> GovernanceEvent:
    """Transition an ACTIVE case to REVOKED, emitting ``ENVELOPE_REVOKED``."""

    return case.transition(
        target=RiskCaseState.REVOKED,
        actor=actor,
        reason=reason,
        now=now,
        event_type=GovernanceEventType.ENVELOPE_REVOKED,
    )


def supersede_case(
    case: RiskDecisionCase,
    *,
    now: datetime,
    reason: str,
    actor: str,
) -> GovernanceEvent:
    """Transition an ACTIVE case to SUPERSEDED after a replacement envelope is minted."""

    return case.transition(
        target=RiskCaseState.SUPERSEDED,
        actor=actor,
        reason=reason,
        now=now,
        event_type=GovernanceEventType.CASE_STATE_CHANGED,
    )


def reconcile_case_state(
    case: RiskDecisionCase,
    *,
    envelope: RiskAuthorizationEnvelope,
    revocation_state: RevocationState,
    now: datetime,
    actor: str = "lifecycle-reconciler",
) -> Optional[GovernanceEvent]:
    """Reconcile an ACTIVE case against current authority state (RA-6 §11).

    Precedence: expiry (time) → revocation (writer state). Returns the emitted
    event, or ``None`` if the case is already terminal or still valid. Never
    reactivates a terminal case (I4): a terminal state simply yields ``None``.
    """

    if case.state is not RiskCaseState.ACTIVE:
        return None

    if now > envelope.expires_at:
        return expire_case_if_elapsed(
            case, expires_at=envelope.expires_at, now=now, actor=actor
        )

    revoked = revocation_state.is_revoked(
        tenant_id=envelope.tenant_id,
        envelope_id=envelope.envelope_id,
        subject_id=envelope.subject,
        model_id=envelope.model_id,
        envelope_epoch=envelope.bindings.authority_epoch,
    )
    if revoked is not None:
        return revoke_case(case, now=now, reason=revoked, actor=actor)
    return None
