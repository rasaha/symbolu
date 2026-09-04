"""Phase 5C action admission seam (ADR Cloud Scaling 5C action admission, D-1, D-3, D-4, D-5).

The only production path from a :class:`RiskAuthorizationEnvelope` to an
:class:`ActionAuthorization`. The case-based :meth:`RiskAuthorityApplication.authorize_action`
stays contained in production mode; this seam composes what the kernel already owns —
the durable envelope store, the verifier, revocation epochs, the key ring, the clock —
around an injected :class:`ActionGatePort` that rules only on the action against the
envelope.

The act, in order:

1. read the clock **once**; that instant is the admission instant;
2. load the envelope for the tenant from the store; refuse an unknown one;
3. **kernel verification** (D-4): signature, validity window, tenant and session
   binding, revocation and authority epoch, through the same
   :class:`~risk_authority.services.envelope_verifier.EnvelopeVerifier` the application
   uses. A failing envelope is refused before any port runs;
4. derive ``authorization_id = auth.v1:sha256(tenant_id, envelope_id, action_digest)``
   (D-3). If an authorization is already stored under it with the same action digest,
   return it as ``REPLAYED`` and touch nothing; a different digest is a conflict;
5. call the port. It may answer ``AUTHORIZED`` or ``DENIED`` and nothing else: any other
   value, an authorization that does not name this id, envelope and action, or an
   exception is recorded as ``DENIED`` (D-4);
6. persist the authorization with ``expires_at`` equal to the envelope's (D-5) and emit
   ``ACTION_AUTHORIZED`` or ``ACTION_DENIED``.

An authorization executes nothing: 5X credentials and an execution reservation are still
required, and :attr:`ActionAuthorization.executable` is a permanently-``False`` property.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from ..crypto.canonical import canonical_bytes
from ..domain.actions import ActionAuthorization, CanonicalAction
from ..domain.enums import ActionGateDecision, AuthorizationDisposition, GovernanceEventType
from ..domain.errors import RiskAuthorityError
from ..domain.events import GovernanceEvent
from ..integrations.actiongate import ActionGatePort, ReferenceActionGate, RuntimeIdentity
from ..persistence.errors import PersistenceConflictError
from ..services.envelope_verifier import EnvelopeVerifier
from .dependencies import RiskAuthorityApplication
from .evaluation_seam import SeamConfigurationError

__all__ = [
    "AUTHORIZATION_ID_PREFIX",
    "derive_authorization_id",
    "ActionAdmissionRequest",
    "ActionAdmissionRefusal",
    "ActionAdmissionOutcome",
    "ActionAdmissionSeam",
]

#: Derived, never allocated: the same tenant, envelope and action always name one authorization.
AUTHORIZATION_ID_PREFIX = "auth.v1:"


def derive_authorization_id(*, tenant_id: str, envelope_id: str, action_digest: str) -> str:
    payload = canonical_bytes(
        {"tenant_id": tenant_id, "envelope_id": envelope_id, "action_digest": action_digest}
    )
    return AUTHORIZATION_ID_PREFIX + hashlib.sha256(payload).hexdigest()


def _token(name: str, value: object) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise RiskAuthorityError(f"{name} must be a non-blank str without surrounding whitespace")


@dataclass(frozen=True)
class ActionAdmissionRequest:
    """What a caller may say. No instant, no decision, no envelope body, no scope."""

    tenant_id: str
    envelope_id: str
    action: CanonicalAction
    session_id: str
    satisfied_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("tenant_id", self.tenant_id)
        _token("envelope_id", self.envelope_id)
        _token("session_id", self.session_id)
        if type(self.action) is not CanonicalAction:
            raise RiskAuthorityError("action must be exactly a CanonicalAction")
        if self.action.tenant_id != self.tenant_id:
            raise RiskAuthorityError("action.tenant_id must equal the request tenant_id")
        if not isinstance(self.satisfied_conditions, tuple) or any(
            type(c) is not str for c in self.satisfied_conditions
        ):
            raise RiskAuthorityError("satisfied_conditions must be a tuple of str")


class ActionAdmissionRefusal(str, Enum):
    """Why the seam stopped before a verdict. A port's ``DENIED`` is a verdict, not a refusal."""

    ENVELOPE_NOT_FOUND = "ENVELOPE_NOT_FOUND"
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    AUTHORIZATION_CONFLICT = "AUTHORIZATION_CONFLICT"


@dataclass(frozen=True)
class ActionAdmissionOutcome:
    """A verdict (``authorization``) or a refusal, at one instant. Never execution."""

    admitted_at: datetime
    authorization: Optional[ActionAuthorization] = None
    refusal: Optional[ActionAdmissionRefusal] = None
    detail: str = ""

    @property
    def admitted(self) -> bool:
        """``True`` iff a verdict exists and it is ``AUTHORIZED``."""

        return self.authorization is not None and self.authorization.authorized

    @property
    def replayed(self) -> bool:
        return (
            self.authorization is not None
            and self.authorization.disposition is AuthorizationDisposition.REPLAYED
        )

    @property
    def executable(self) -> bool:
        """Always ``False``: admission is not execution (5X, 5D pending)."""

        return False


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


class ActionAdmissionSeam:
    """Compose the kernel into a verification-first, replay-safe action admission."""

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        gate: ActionGatePort,
        clock: Callable[[], datetime],
        production: bool,
    ) -> None:
        self._app = app
        self._gate = gate
        self._clock = clock
        self._production = production
        self._verifier = EnvelopeVerifier()

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(
        cls,
        *,
        app: RiskAuthorityApplication,
        gate: ActionGatePort,
        clock: Callable[[], datetime],
    ) -> "ActionAdmissionSeam":
        """Build a production seam. Fails closed on any reference-grade dependency (D-4)."""

        if getattr(app, "_production_mode", False) is not True:
            raise SeamConfigurationError(
                "production admission seam requires a RiskAuthorityApplication in production "
                "mode standing on the durable store that holds the envelope")
        if isinstance(gate, ReferenceActionGate):
            raise SeamConfigurationError(
                "production admission seam refuses ReferenceActionGate and any subclass of it; "
                "the reference gate is a conformance component, never production enforcement")
        if getattr(gate, "is_production_authoritative", False) is not True or not callable(
            getattr(gate, "authorize", None)
        ):
            raise SeamConfigurationError(
                "production admission seam requires an ActionGatePort declaring "
                "is_production_authoritative=True; silence is refusal")
        if not callable(clock):
            raise SeamConfigurationError("clock must be a callable returning an aware datetime")
        return cls(app=app, gate=gate, clock=clock, production=True)

    @classmethod
    def reference(
        cls,
        *,
        app: RiskAuthorityApplication,
        clock: Callable[[], datetime],
        gate: Optional[ActionGatePort] = None,
    ) -> "ActionAdmissionSeam":
        """A labelled conformance seam over the in-package reference gate. Never production."""

        if getattr(app, "_production_mode", False) is True:
            raise SeamConfigurationError(
                "the reference admission seam cannot be built over a production application")
        return cls(app=app, gate=gate if gate is not None else ReferenceActionGate(),
                   clock=clock, production=False)

    @property
    def is_production(self) -> bool:
        return self._production

    # ------------------------------------------------------------------ the act
    def issue(self, request: ActionAdmissionRequest) -> ActionAdmissionOutcome:
        if not isinstance(request, ActionAdmissionRequest):
            raise RiskAuthorityError("issue requires an ActionAdmissionRequest")
        now = self._clock()  # the one clock read of this act
        if not _is_aware(now):
            raise RiskAuthorityError("the injected clock must return a timezone-aware instant")

        def refuse(reason: ActionAdmissionRefusal, detail: str) -> ActionAdmissionOutcome:
            return ActionAdmissionOutcome(admitted_at=now, refusal=reason, detail=detail)

        # 2. The envelope, from the store, under this tenant.
        envelope = self._app.envelopes.get(request.tenant_id, request.envelope_id)
        if envelope is None:
            return refuse(ActionAdmissionRefusal.ENVELOPE_NOT_FOUND,
                          "no envelope under this tenant and id")
        # 3. Kernel verification before any port runs (D-4).
        verification = self._verifier.verify(
            envelope=envelope,
            key_ring=self._app._key_ring,
            revocation_state=self._app.revocation,
            now=now,
            expected_tenant=request.tenant_id,
            expected_session=request.session_id,
        )
        if not verification.valid:
            return refuse(ActionAdmissionRefusal.ENVELOPE_INVALID, "; ".join(verification.reasons))
        # 4. Derived identity and replay (D-3).
        action = request.action
        authorization_id = derive_authorization_id(
            tenant_id=request.tenant_id, envelope_id=envelope.envelope_id,
            action_digest=action.digest)
        stored = self._app.authorizations.get(request.tenant_id, authorization_id)
        if stored is not None:
            if stored.action_digest != action.digest:
                return refuse(ActionAdmissionRefusal.AUTHORIZATION_CONFLICT,
                              "a stored authorization under this id names another action")
            return ActionAdmissionOutcome(
                admitted_at=now,
                authorization=replace(stored, disposition=AuthorizationDisposition.REPLAYED),
                detail="stored verdict returned; nothing minted")
        # 5. The port rules on the action against the envelope; AUTHORIZED or DENIED only.
        identity = RuntimeIdentity(tenant_id=request.tenant_id, actor_id=action.actor_id,
                                   model_id=action.model_id, session_id=request.session_id)
        verdict = self._rule(authorization_id, envelope, action, identity, now,
                             frozenset(request.satisfied_conditions))
        # 6. Persist and emit (D-5).
        try:
            self._app.authorizations.save(verdict)
        except PersistenceConflictError as exc:
            return refuse(ActionAdmissionRefusal.AUTHORIZATION_CONFLICT, str(exc))
        self._app.metrics.incr("actiongate.requests")
        self._app.metrics.incr("actiongate.authorized" if verdict.authorized else "actiongate.denied")
        self._app._publish(GovernanceEvent(
            event_id=f"evt_{verdict.authorization_id}",
            tenant_id=request.tenant_id,
            event_type=(GovernanceEventType.ACTION_AUTHORIZED if verdict.authorized
                        else GovernanceEventType.ACTION_DENIED),
            aggregate_id=envelope.envelope_id,
            actor=action.actor_id,
            timestamp=now,
            payload_digest=action.digest,
        ))
        return ActionAdmissionOutcome(admitted_at=now, authorization=verdict)

    def _rule(self, authorization_id, envelope, action, identity, now, satisfied
              ) -> ActionAuthorization:
        def denied(*reasons: str) -> ActionAuthorization:
            return ActionAuthorization(
                authorization_id=authorization_id, envelope_id=envelope.envelope_id,
                action_digest=action.digest, decision=ActionGateDecision.DENIED,
                tenant_id=action.tenant_id, reason_codes=tuple(reasons),
                expires_at=envelope.expires_at, disposition=AuthorizationDisposition.ADMITTED)

        try:
            result = self._gate.authorize(
                authorization_id=authorization_id, envelope=envelope, action=action,
                identity=identity, key_ring=self._app._key_ring,
                revocation_state=self._app.revocation, now=now,
                satisfied_conditions=satisfied)
        except Exception as exc:  # noqa: BLE001 — a failing gate is never a pass (D-4)
            return denied(f"gate raised {type(exc).__name__}")
        if type(result) is not ActionAuthorization:
            return denied("gate returned a foreign result type")
        if result.decision not in (ActionGateDecision.AUTHORIZED, ActionGateDecision.DENIED):
            return denied(f"gate returned {getattr(result.decision, 'value', result.decision)!r}; "
                          "only AUTHORIZED or DENIED is admitted")
        if (result.authorization_id != authorization_id or result.envelope_id != envelope.envelope_id
                or result.action_digest != action.digest
                or result.tenant_id not in ("", action.tenant_id)):
            return denied("gate result does not name this authorization, envelope and action")
        return replace(result, tenant_id=action.tenant_id, expires_at=envelope.expires_at,
                       disposition=AuthorizationDisposition.ADMITTED)
