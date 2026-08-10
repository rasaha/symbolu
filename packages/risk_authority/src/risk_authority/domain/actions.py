"""Canonical actions and their digests (spec §14, user brief §11).

ActionGate authorizes a *canonical action*, never an arbitrary transport
serialization. The digest is computed over the canonical form so a payload
mutated after authorization is detectable at the executor (spec §29 payload
binding, AC-07).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..crypto.hashing import digest
from .enums import ActionGateDecision

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
    expires_at: Optional[object] = None  # datetime; kept Optional for RA-4

    @property
    def authorized(self) -> bool:
        return self.decision is ActionGateDecision.AUTHORIZED
