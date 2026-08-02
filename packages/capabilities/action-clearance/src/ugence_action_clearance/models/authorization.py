"""Authorization context + exact authorized-action identity (design §12).

These carry the ActionGate/Decision-Authority authorization by **reference and
fingerprint only** — the neutral core never imports Decision Authority or the
ActionGate provider. The action identity is domain-neutral: GitHub/K8s/DB/robotics
values may appear only as normalized profile-supplied parameters or target
identity, never hardcoded here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from ..errors import ValidationError
from ..fingerprinting import authorized_action_fingerprint
from .constraints import EffectiveConstraint


@dataclass(frozen=True)
class AuthorizedActionIdentity:
    """The exact, neutral identity of the already-authorized action."""

    authorized_action_fingerprint: str
    action_type: str
    target_ref: str
    operation: str
    actor_ref: Optional[str] = None
    artifact_ref: Optional[str] = None
    artifact_fingerprint: Optional[str] = None
    parameters: Mapping[str, str] = field(default_factory=dict)
    action_governance_request_ref: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("authorized_action_fingerprint", "action_type", "target_ref", "operation"):
            if not getattr(self, name):
                raise ValidationError(f"AuthorizedActionIdentity.{name} must be non-empty")

    @property
    def computed_fingerprint(self) -> str:
        """Deterministic fingerprint over the exact-action identity fields."""
        return authorized_action_fingerprint({
            "action_type": self.action_type,
            "target_ref": self.target_ref,
            "operation": self.operation,
            "actor_ref": self.actor_ref,
            "artifact_ref": self.artifact_ref,
            "artifact_fingerprint": self.artifact_fingerprint,
            "parameters": dict(self.parameters),
        })


@dataclass(frozen=True)
class AuthorizationContext:
    """A minimal projection of the ActionGate authorization (by ref + fingerprint)."""

    authorization_ref: str
    authorization_result_fingerprint: str
    authorization_outcome: str
    authorization_issued_at: datetime
    authorization_expires_at: datetime
    tenant_id: str
    authorization_constraints: Tuple[str, ...] = ()
    authorization_obligations: Tuple[str, ...] = ()
    decision_record_ref: str = ""
    context_envelope_ref: str = ""
    context_envelope_hash: str = ""
    authorized_actor_basis: str = ""
    policy_refs: Tuple[str, ...] = ()
    override_ref: Optional[str] = None
    supersedes_ref: Optional[str] = None
    # optional structured constraints for provable narrowing (§20)
    structured_constraints: Tuple[EffectiveConstraint, ...] = ()

    def __post_init__(self) -> None:
        if not self.authorization_ref:
            raise ValidationError("AuthorizationContext.authorization_ref must be non-empty")


__all__ = ["AuthorizedActionIdentity", "AuthorizationContext"]
