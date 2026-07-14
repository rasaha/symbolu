"""ControlAuthorization envelope + reference authorizer + commit revalidator.

A ``ControlAuthorization`` binds a single decision to the *exact* action identity,
world-state version, and constraint-set version it was granted against, with a
freshness bound. This is a REFERENCE control-plane authorization object: its
``grant_id`` is a deterministic content identity, NOT a production cryptographic
signature. No crypto enforcement is claimed in Phase 0.

Fail-closed contract:
* only ``EXECUTE`` / ``EXECUTE_WITH_CONSTRAINTS`` decisions can be authorized;
* every other decision yields ``None`` (no grant);
* commit-time revalidation rejects any drift in world/constraint version, any
  expiry, and any action-identity mismatch.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from .envelopes import ActionDecision, CanonicalActionCandidate
from .errors import (AuthorizationBindingError, SchemaValidationError,
                     StaleAuthorizationError)
from .identity import identity, normalize_float
from .world_state import CanonicalWorldState

_DOMAIN = "control_authorization"

_AUTHORIZABLE = frozenset({ActionDecision.EXECUTE,
                           ActionDecision.EXECUTE_WITH_CONSTRAINTS})


@dataclass(frozen=True)
class ControlAuthorization:
    """One-shot authorization bound to an exact action + state + constraints."""
    decision_id: str
    action_identity: str            # identity of the authorized candidate
    world_state_version: str        # exact world-state version at grant time
    constraint_set_version: str     # exact constraint-set version at grant time
    decision: ActionDecision
    issued_time_s: float
    expiry_time_s: float            # freshness bound
    permitted_constraints: Tuple[str, ...] = ()   # execution caps, if any

    def __post_init__(self) -> None:
        if not self.decision_id or not self.action_identity:
            raise SchemaValidationError("decision_id/action_identity required")
        if self.decision not in _AUTHORIZABLE:
            raise SchemaValidationError(
                "ControlAuthorization can only wrap EXECUTE / "
                "EXECUTE_WITH_CONSTRAINTS")
        normalize_float(self.issued_time_s, field="issued_time_s")
        normalize_float(self.expiry_time_s, field="expiry_time_s")
        if self.expiry_time_s < self.issued_time_s:
            raise SchemaValidationError("expiry_time_s must be >= issued_time_s")
        if not isinstance(self.permitted_constraints, tuple):
            raise SchemaValidationError("permitted_constraints must be a tuple")

    @property
    def grant_id(self) -> str:
        """Deterministic content identity of this authorization (reference)."""
        return identity(self, domain=_DOMAIN)


class ReferenceControlAuthorizer:
    """Mints authorizations only for executable decisions; else refuses."""

    def authorize(
        self,
        *,
        decision: ActionDecision,
        candidate: Optional[CanonicalActionCandidate],
        world_state: CanonicalWorldState,
        constraint_set_version: str,
        decision_id: str,
        issued_time_s: float,
        ttl_s: float,
        permitted_constraints: Tuple[str, ...] = (),
    ) -> Optional[ControlAuthorization]:
        # Fail closed: nothing but a positive, candidate-backed executable
        # decision produces a grant.
        if decision not in _AUTHORIZABLE:
            return None
        if candidate is None:
            raise AuthorizationBindingError(
                "cannot authorize an executable decision without a candidate")
        if ttl_s < 0:
            raise SchemaValidationError("ttl_s must be >= 0")
        return ControlAuthorization(
            decision_id=decision_id,
            action_identity=candidate.identity,
            world_state_version=world_state.version,
            constraint_set_version=constraint_set_version,
            decision=decision,
            issued_time_s=issued_time_s,
            expiry_time_s=issued_time_s + ttl_s,
            permitted_constraints=permitted_constraints,
        )


class ReferenceCommitRevalidator:
    """Commit-time TOCTOU check. Rejects any drift, expiry, or rebinding."""

    def revalidate(
        self,
        *,
        authorization: ControlAuthorization,
        candidate: CanonicalActionCandidate,
        current_world_state: CanonicalWorldState,
        current_constraint_set_version: str,
        now_s: float,
    ) -> None:
        """Raise on any mismatch; return None if the grant is still valid."""
        if candidate.identity != authorization.action_identity:
            raise AuthorizationBindingError(
                "authorization does not bind this candidate (action changed)")
        if current_world_state.version != authorization.world_state_version:
            raise StaleAuthorizationError(
                "world-state version changed since authorization")
        if current_constraint_set_version != authorization.constraint_set_version:
            raise StaleAuthorizationError(
                "constraint-set version changed since authorization")
        if now_s > authorization.expiry_time_s:
            raise StaleAuthorizationError("authorization expired")
