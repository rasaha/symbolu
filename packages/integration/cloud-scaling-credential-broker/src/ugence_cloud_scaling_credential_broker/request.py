"""The credential request: package-minted, token-guarded, digest-bound (ADR 5X, D-2).

A :class:`CredentialRequest` cannot be assembled by a caller: its ``minting_token`` must be
this module's private object, which the curated API does not export. It is minted only by
:class:`CredentialRequestMinter` from an ``AUTHORIZED`` ``ActionAuthorization``, a
``RESERVED`` ``ExecutionReservation`` whose key names that authorization, the envelope the
authorization was admitted under, and a presented ``ExecutionTargetScope`` whose fixed D-2
mapping re-derives the authorized action digest. It carries no instant of its own choosing:
``issued_at`` and ``not_after`` are handed in by the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from risk_authority.crypto.canonical import canonical_bytes
from risk_authority.crypto.hashing import sha256_hex
from risk_authority.domain.actions import ActionAuthorization
from risk_authority.domain.enums import ActionGateDecision
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from ugence_cloud_scaling_action_admission import capacity_action_to_canonical
from ugence_cloud_scaling_authorization_contracts import ExecutionTargetScope
from ugence_execution_reservation import ExecutionKey, ExecutionReservation, ReservationState

from .errors import CredentialBrokerContractError, CredentialRequestRefused
from .identifiers import REQUEST_DIGEST_PREFIX
from .role import RoleStatement, derive_least_privilege_role

__all__ = ["CredentialRefusal", "CredentialRequest", "CredentialRequestMinter", "derive_request_digest"]

#: The private minting token. Not exported, not in ``__all__``, not reachable from the API.
_MINT_TOKEN = object()


class CredentialRefusal(str, Enum):
    """Why no credential was materialized. A broker's own failure is ``BROKER_UNAVAILABLE``."""

    AUTHORIZATION_NOT_FOUND = "AUTHORIZATION_NOT_FOUND"
    AUTHORIZATION_NOT_AUTHORIZED = "AUTHORIZATION_NOT_AUTHORIZED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    ENVELOPE_NOT_FOUND = "ENVELOPE_NOT_FOUND"
    ENVELOPE_EXPIRED = "ENVELOPE_EXPIRED"
    RESERVATION_NOT_FOUND = "RESERVATION_NOT_FOUND"
    RESERVATION_NOT_RESERVED = "RESERVATION_NOT_RESERVED"
    RESERVATION_MISMATCH = "RESERVATION_MISMATCH"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    TARGET_SCOPE_MISMATCH = "TARGET_SCOPE_MISMATCH"
    NO_CREDENTIAL_REQUIRED = "NO_CREDENTIAL_REQUIRED"
    WINDOW_INVALID = "WINDOW_INVALID"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
    GRANT_INVALID = "GRANT_INVALID"
    GRANT_CONFLICT = "GRANT_CONFLICT"


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class CredentialRequest:
    """What the broker is handed, and all it is handed."""

    tenant_id: str
    authorization_ref: str
    execution_key: ExecutionKey
    target_scope_digest: str
    reservation_id: str
    envelope_id: str
    role: RoleStatement
    issued_at: datetime
    not_after: datetime
    request_digest: str
    minting_token: object = None

    def __post_init__(self) -> None:
        if self.minting_token is not _MINT_TOKEN:
            raise CredentialBrokerContractError(
                "CredentialRequest cannot be constructed directly. It is minted only by "
                "CredentialRequestMinter from an authorized, reserved action; there is no "
                "supported route from caller-chosen fields to a credential request.")
        if type(self.execution_key) is not ExecutionKey or type(self.role) is not RoleStatement:
            raise CredentialBrokerContractError("CredentialRequest carries foreign types")
        if not (_is_aware(self.issued_at) and _is_aware(self.not_after)) or not self.issued_at < self.not_after:
            raise CredentialBrokerContractError("CredentialRequest window must be aware and half-open")
        if self.request_digest != derive_request_digest(self.to_canonical_dict()):
            raise CredentialBrokerContractError("CredentialRequest.request_digest does not re-derive")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "authorization_ref": self.authorization_ref,
            "execution_key": self.execution_key.identity,
            "target_scope_digest": self.target_scope_digest,
            "reservation_id": self.reservation_id,
            "envelope_id": self.envelope_id,
            "role": self.role,
            "issued_at": self.issued_at,
            "not_after": self.not_after,
        }


def derive_request_digest(body: dict[str, Any]) -> str:
    return REQUEST_DIGEST_PREFIX + sha256_hex(canonical_bytes(body))[len("sha256:"):]


class CredentialRequestMinter:
    """The one route to a :class:`CredentialRequest`. Stateless; reads no clock."""

    def mint(
        self,
        *,
        authorization: ActionAuthorization,
        reservation: ExecutionReservation,
        envelope: RiskAuthorizationEnvelope,
        target_scope: ExecutionTargetScope,
        issued_at: datetime,
        not_after: datetime,
    ) -> CredentialRequest:
        R = CredentialRefusal
        if type(authorization) is not ActionAuthorization:
            raise CredentialRequestRefused(R.AUTHORIZATION_NOT_FOUND, "authorization is not an ActionAuthorization")
        if authorization.decision is not ActionGateDecision.AUTHORIZED:
            raise CredentialRequestRefused(R.AUTHORIZATION_NOT_AUTHORIZED,
                                           f"authorization decision is {authorization.decision.value}")
        if type(envelope) is not RiskAuthorizationEnvelope or envelope.envelope_id != authorization.envelope_id \
                or envelope.tenant_id != authorization.tenant_id:
            raise CredentialRequestRefused(R.ENVELOPE_NOT_FOUND, "envelope does not match the authorization")
        if type(reservation) is not ExecutionReservation:
            raise CredentialRequestRefused(R.RESERVATION_NOT_FOUND, "reservation is not an ExecutionReservation")
        if reservation.state is not ReservationState.RESERVED:
            raise CredentialRequestRefused(R.RESERVATION_NOT_RESERVED,
                                           f"reservation state is {reservation.state.value}")
        key = reservation.execution_key
        if (key.tenant_id != authorization.tenant_id
                or key.authorization_ref != authorization.authorization_id
                or reservation.authorization_ref != authorization.authorization_id
                or key.authorized_action_fingerprint != authorization.action_digest
                or reservation.action_fingerprint != authorization.action_digest):
            raise CredentialRequestRefused(R.RESERVATION_MISMATCH,
                                           "reservation key does not name this authorization and action")
        try:
            action = capacity_action_to_canonical(envelope, target_scope)
        except Exception as exc:  # noqa: BLE001 — a scope that cannot map is not this action's
            raise CredentialRequestRefused(R.TARGET_SCOPE_MISMATCH, f"{type(exc).__name__}") from exc
        if action.digest != authorization.action_digest:
            raise CredentialRequestRefused(R.TARGET_SCOPE_MISMATCH,
                                           "presented target scope does not re-derive the authorized action")
        if key.target_ref != target_scope.digest() or key.operation != target_scope.action_type:
            raise CredentialRequestRefused(R.RESERVATION_MISMATCH,
                                           "reservation key names another target or operation")
        role = derive_least_privilege_role(target_scope)
        if role is None:
            raise CredentialRequestRefused(R.NO_CREDENTIAL_REQUIRED,
                                           f"{target_scope.action_type!r} changes nothing and derives no credential")
        if not (_is_aware(issued_at) and _is_aware(not_after)) or not issued_at < not_after:
            raise CredentialRequestRefused(R.WINDOW_INVALID, "no validity remains for a credential")
        body = {
            "tenant_id": authorization.tenant_id,
            "authorization_ref": authorization.authorization_id,
            "execution_key": key.identity,
            "target_scope_digest": target_scope.digest(),
            "reservation_id": reservation.reservation_id,
            "envelope_id": envelope.envelope_id,
            "role": role,
            "issued_at": issued_at,
            "not_after": not_after,
        }
        return CredentialRequest(
            tenant_id=authorization.tenant_id,
            authorization_ref=authorization.authorization_id,
            execution_key=key,
            target_scope_digest=target_scope.digest(),
            reservation_id=reservation.reservation_id,
            envelope_id=envelope.envelope_id,
            role=role,
            issued_at=issued_at,
            not_after=not_after,
            request_digest=derive_request_digest(body),
            minting_token=_MINT_TOKEN,
        )
