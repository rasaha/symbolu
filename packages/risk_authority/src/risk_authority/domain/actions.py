"""Canonical actions and their digests (spec §14, user brief §11).

ActionGate authorizes a *canonical action*, never an arbitrary transport
serialization. The digest is computed over the canonical form so a payload
mutated after authorization is detectable at the executor (spec §29 payload
binding, AC-07).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..crypto.hashing import digest
from .enums import ActionGateDecision, AuthorizationDisposition

__all__ = ["CanonicalAction", "ActionAuthorization", "action_digest"]


@dataclass(frozen=True)
class CanonicalAction:
    """A normalized, deterministic representation of a requested action."""

    tenant_id: str
    actor_id: str
    model_id: str
    action_type: str
    target_id: str
    purpose: str
    data_classes: tuple[str, ...] = ()
    destination: str = ""
    amount_minor_units: Optional[int] = None
    currency: str = ""

    @property
    def digest(self) -> str:
        return action_digest(self)


def action_digest(action: CanonicalAction) -> str:
    """Stable ``sha256:<hex>`` digest over the canonical action."""

    return digest(action)


@dataclass(frozen=True)
class ActionAuthorization:
    """ActionGate's outcome, bound to the exact action digest (spec §15)."""

    authorization_id: str
    envelope_id: str
    action_digest: str
    decision: ActionGateDecision
    tenant_id: str = ""
    reason_codes: tuple[str, ...] = ()
    trajectory_version: Optional[int] = None
    #: The envelope's own expiry (Phase 5C, D-5); ``None`` only on the RA-4 reference path.
    expires_at: Optional[datetime] = None
    #: ``ADMITTED`` for a fresh verdict, ``REPLAYED`` when the stored verdict for the same
    #: ``(tenant, envelope, action digest)`` was returned again (Phase 5C, D-3).
    disposition: AuthorizationDisposition = AuthorizationDisposition.ADMITTED

    def __post_init__(self) -> None:
        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise TypeError("ActionAuthorization.expires_at must be a datetime or None")
        if not isinstance(self.decision, ActionGateDecision):
            raise TypeError("ActionAuthorization.decision must be an ActionGateDecision")
        if not isinstance(self.disposition, AuthorizationDisposition):
            raise TypeError("ActionAuthorization.disposition must be an AuthorizationDisposition")

    @property
    def authorized(self) -> bool:
        return self.decision is ActionGateDecision.AUTHORIZED

    @property
    def executable(self) -> bool:
        """Always ``False``: an authorization is admission, never execution (5X, 5D pending)."""

        return False
