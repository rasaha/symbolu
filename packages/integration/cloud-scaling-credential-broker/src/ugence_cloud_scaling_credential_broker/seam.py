"""The Credential Broker seam (ADR 5X, D-1 … D-5): one act, one clock read, one grant.

The act, in order:

1. read the clock **once**; that instant is ``issued_at``;
2. load the authorization and its envelope from the Risk Authority application; refuse an
   unknown, non-``AUTHORIZED`` or expired authorization and an expired envelope;
3. load the reservation from the reservation port; refuse one that is not ``RESERVED``,
   whose lease has expired, or whose key names another authorization, action, target or
   operation;
4. re-derive the authorized action from the presented target scope through the fixed D-2
   mapping; refuse a scope that does not re-derive the authorized digest;
5. derive the least-privilege role; ``no_change`` derives nothing and is refused;
6. ``not_after = min(authorization.expires_at, lease.expires_at, envelope.expires_at,
   issued_at + ttl_cap)``; refuse an empty window;
7. mint the request; derive the grant id; return a stored grant for the same request as
   ``REPLAYED`` and touch nothing;
8. call the broker; a raising broker is ``BROKER_UNAVAILABLE``; a grant that names another
   request, broker or profile, exceeds the window, or widens the role is ``GRANT_INVALID``;
9. persist the grant and return it.

A grant is a handle reference: consuming it is 5D's, and LIVE execution stays blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Callable, Optional

from risk_authority.api import RiskAuthorityApplication
from risk_authority.domain.enums import ActionGateDecision
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope
from ugence_execution_reservation import (
    ExecutionReservationPort,
    InMemoryExecutionReservationStore,
    ReservationState,
)

from .broker import CredentialBrokerPort, ReferenceCredentialBroker
from .errors import (
    CredentialBrokerConfigurationError,
    CredentialBrokerContractError,
    CredentialBrokerExactTypeError,
    CredentialRequestRefused,
)
from .grant import CredentialGrant, CredentialGrantStore, GrantDisposition, InMemoryCredentialGrantStore, derive_grant_id
from .identifiers import DEFAULT_TTL_CAP, MAX_TTL_CAP
from .request import CredentialRefusal, CredentialRequestMinter
from .role import role_widening

__all__ = ["CredentialMaterializationRequest", "CredentialMaterializationOutcome", "CredentialBrokerSeam"]


def _token(name: str, value: object) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise CredentialBrokerExactTypeError(f"{name} must be a non-blank str without surrounding whitespace")


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class CredentialMaterializationRequest:
    """What a caller may say. No instant, no role, no window, no handle."""

    tenant_id: str
    authorization_id: str
    reservation_id: str
    target_scope: ExecutionTargetScope

    def __post_init__(self) -> None:
        _token("tenant_id", self.tenant_id)
        _token("authorization_id", self.authorization_id)
        _token("reservation_id", self.reservation_id)
        if type(self.target_scope) is not ExecutionTargetScope:
            raise CredentialBrokerExactTypeError("target_scope must be exactly an ExecutionTargetScope")
        if self.target_scope.tenant_id != self.tenant_id:
            raise CredentialBrokerExactTypeError("target_scope.tenant_id must equal the request tenant_id")


@dataclass(frozen=True)
class CredentialMaterializationOutcome:
    """A grant or a typed refusal, at one instant. Never execution."""

    materialized_at: datetime
    grant: Optional[CredentialGrant] = None
    refusal: Optional[CredentialRefusal] = None
    detail: str = ""
    request_digest: str = ""

    @property
    def materialized(self) -> bool:
        return self.grant is not None

    @property
    def replayed(self) -> bool:
        return self.grant is not None and self.grant.disposition is GrantDisposition.REPLAYED

    @property
    def executable(self) -> bool:
        """Always ``False``: a grant is a handle; LIVE execution is blocked until 5D."""

        return False


class CredentialBrokerSeam:
    """Compose the ladder's last authority step. Construct via ``production`` or ``reference``."""

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        reservations: ExecutionReservationPort,
        broker: CredentialBrokerPort,
        grants: CredentialGrantStore,
        clock: Callable[[], datetime],
        ttl_cap: timedelta,
        production: bool,
    ) -> None:
        if not isinstance(app, RiskAuthorityApplication):
            raise CredentialBrokerConfigurationError("a RiskAuthorityApplication is required")
        if not callable(getattr(reservations, "get_reservation", None)):
            raise CredentialBrokerConfigurationError("reservations must implement ExecutionReservationPort")
        if not callable(getattr(broker, "materialize", None)):
            raise CredentialBrokerConfigurationError("broker must implement CredentialBrokerPort")
        if not callable(getattr(grants, "get", None)) or not callable(getattr(grants, "save", None)):
            raise CredentialBrokerConfigurationError("grants must implement CredentialGrantStore")
        if not callable(clock):
            raise CredentialBrokerConfigurationError("clock must be a callable returning a datetime")
        if type(ttl_cap) is not timedelta or ttl_cap <= timedelta(0) or ttl_cap > MAX_TTL_CAP:
            raise CredentialBrokerConfigurationError(
                f"ttl_cap must be a positive timedelta of at most {MAX_TTL_CAP} (ADR 5X, D-4)")
        self._app = app
        self._reservations = reservations
        self._broker = broker
        self._grants = grants
        self._clock = clock
        self._ttl_cap = ttl_cap
        self._production = production
        self._minter = CredentialRequestMinter()

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(
        cls,
        *,
        app: RiskAuthorityApplication,
        reservations: ExecutionReservationPort,
        broker: CredentialBrokerPort,
        grants: CredentialGrantStore,
        clock: Callable[[], datetime],
        ttl_cap: timedelta = DEFAULT_TTL_CAP,
    ) -> "CredentialBrokerSeam":
        """Production seam. Fails closed on any reference-grade dependency (D-1, D-5)."""

        if getattr(app, "_production_mode", False) is not True:
            raise CredentialBrokerConfigurationError(
                "production brokering requires a RiskAuthorityApplication in production mode")
        if isinstance(broker, ReferenceCredentialBroker) or (
                getattr(broker, "is_production_authoritative", False) is not True):
            raise CredentialBrokerConfigurationError(
                "production brokering requires a production-authoritative CredentialBrokerPort; "
                "the reference broker is refused (D-1)")
        if isinstance(reservations, InMemoryExecutionReservationStore) or (
                getattr(reservations, "production_mode", False) is not True
                and getattr(reservations, "is_production_authoritative", False) is not True):
            raise CredentialBrokerConfigurationError(
                "production brokering requires a production-mode execution reservation store; "
                "the in-memory ledger is refused")
        if getattr(grants, "is_production_authoritative", False) is not True:
            raise CredentialBrokerConfigurationError(
                "production brokering requires a production-authoritative CredentialGrantStore; "
                "the in-memory store is refused (D-5)")
        return cls(app=app, reservations=reservations, broker=broker, grants=grants, clock=clock,
                   ttl_cap=ttl_cap, production=True)

    @classmethod
    def reference(
        cls,
        *,
        app: RiskAuthorityApplication,
        reservations: ExecutionReservationPort,
        clock: Callable[[], datetime],
        broker: Optional[CredentialBrokerPort] = None,
        grants: Optional[CredentialGrantStore] = None,
        ttl_cap: timedelta = DEFAULT_TTL_CAP,
    ) -> "CredentialBrokerSeam":
        """A labelled conformance seam over the inert reference broker. Never production."""

        if getattr(app, "_production_mode", False) is True:
            raise CredentialBrokerConfigurationError(
                "the reference seam cannot be built over a production application")
        return cls(app=app, reservations=reservations,
                   broker=broker if broker is not None else ReferenceCredentialBroker(),
                   grants=grants if grants is not None else InMemoryCredentialGrantStore(),
                   clock=clock, ttl_cap=ttl_cap, production=False)

    @property
    def is_production(self) -> bool:
        return self._production

    @property
    def ttl_cap(self) -> timedelta:
        return self._ttl_cap

    # ------------------------------------------------------------------ the act
    def materialize(self, request: CredentialMaterializationRequest) -> CredentialMaterializationOutcome:
        if type(request) is not CredentialMaterializationRequest:
            raise CredentialBrokerExactTypeError("materialize requires a CredentialMaterializationRequest")
        now = self._clock()  # the one clock read of this act
        if not _is_aware(now):
            raise CredentialBrokerContractError("the injected clock must return a timezone-aware instant")
        R = CredentialRefusal

        def refuse(reason: CredentialRefusal, detail: str, digest: str = "") -> CredentialMaterializationOutcome:
            return CredentialMaterializationOutcome(materialized_at=now, refusal=reason, detail=detail,
                                                    request_digest=digest)

        # 2. The authorization and its envelope.
        authorization = self._app.authorizations.get(request.tenant_id, request.authorization_id)
        if authorization is None:
            return refuse(R.AUTHORIZATION_NOT_FOUND, "no authorization under this tenant and id")
        if authorization.decision is not ActionGateDecision.AUTHORIZED:
            return refuse(R.AUTHORIZATION_NOT_AUTHORIZED, f"decision is {authorization.decision.value}")
        if authorization.expires_at is None or now > authorization.expires_at:
            return refuse(R.AUTHORIZATION_EXPIRED, "authorization has expired or carries no expiry")
        envelope = self._app.envelopes.get(request.tenant_id, authorization.envelope_id)
        if envelope is None:
            return refuse(R.ENVELOPE_NOT_FOUND, "the authorization's envelope is not in the store")
        if now > envelope.expires_at:
            return refuse(R.ENVELOPE_EXPIRED, "the envelope has expired")
        # 3. The reservation.
        reservation = self._reservations.get_reservation(request.reservation_id)
        if reservation is None or reservation.tenant_id != request.tenant_id:
            return refuse(R.RESERVATION_NOT_FOUND, "no reservation under this tenant and id")
        if reservation.state is not ReservationState.RESERVED:
            return refuse(R.RESERVATION_NOT_RESERVED, f"reservation state is {reservation.state.value}")
        if reservation.lease.is_expired_at(now):
            return refuse(R.LEASE_EXPIRED, "the reservation lease has expired")
        # 6. The window, before minting, so the request carries it.
        not_after = min(authorization.expires_at, reservation.lease.expires_at, envelope.expires_at,
                        now + self._ttl_cap)
        # 4, 5, 7. Mint: re-derives the action, derives the role, refuses typed.
        try:
            credential_request = self._minter.mint(
                authorization=authorization, reservation=reservation, envelope=envelope,
                target_scope=request.target_scope, issued_at=now, not_after=not_after)
        except CredentialRequestRefused as exc:
            return refuse(exc.refusal, exc.detail)
        digest = credential_request.request_digest
        grant_id = derive_grant_id(digest)
        stored = self._grants.get(request.tenant_id, grant_id)
        if stored is not None:
            if stored.request_digest != digest:
                return refuse(R.GRANT_CONFLICT, "a stored grant under this id names another request", digest)
            return CredentialMaterializationOutcome(
                materialized_at=now, grant=replace(stored, disposition=GrantDisposition.REPLAYED),
                detail="stored grant returned; nothing materialized", request_digest=digest)
        # 8. The broker.
        try:
            grant = self._broker.materialize(credential_request)
        except Exception as exc:  # noqa: BLE001 — a failing broker is never a grant
            return refuse(R.BROKER_UNAVAILABLE, f"broker raised {type(exc).__name__}", digest)
        problem = self._grant_problem(grant, grant_id, credential_request, now, not_after)
        if problem:
            return refuse(R.GRANT_INVALID, problem, digest)
        # 9. Persist.
        try:
            self._grants.save(grant)
        except CredentialBrokerContractError as exc:
            return refuse(R.GRANT_CONFLICT, str(exc), digest)
        return CredentialMaterializationOutcome(materialized_at=now, grant=grant, request_digest=digest)

    def _grant_problem(self, grant, grant_id, credential_request, now, not_after) -> str:
        if type(grant) is not CredentialGrant:
            return "broker returned a foreign result type"
        if grant.grant_id != grant_id or grant.request_digest != credential_request.request_digest \
                or grant.tenant_id != credential_request.tenant_id:
            return "grant does not name this request"
        if grant.broker_authority_id != self._broker.broker_authority_id \
                or grant.credential_profile != self._broker.credential_profile:
            return "grant names another broker or profile than the one asked"
        if grant.disposition is not GrantDisposition.MATERIALIZED:
            return "a fresh grant must be MATERIALIZED"
        if grant.validity.issued_at != now or grant.validity.expires_at > not_after \
                or not grant.validity.is_valid_at(now):
            return "grant validity exceeds the ratified window"
        widening = role_widening(grant.role, credential_request.role)
        if widening:
            return "; ".join(widening)
        return ""
