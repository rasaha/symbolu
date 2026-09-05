"""The role grant — what the directory holds, and the only thing it reports.

A grant is bounded by a
:class:`~ugence_governance_contracts.contracts.validity.Validity` and evaluated with
``status_at(as_of)`` at a caller-supplied instant. **A grant outside its window is
absent from every answer** — not reported and flagged — so a lapsed role cannot be
argued around downstream. Revocation is the same: forward-only, and from the revoking
instant the grant is simply gone from the answers.

``role`` and ``scope`` are free, uninterpreted labels, in the same spirit as Decision
Authority's ``VersionedRef.kind``
(``packages/capabilities/decision-authority/.../decisions/subject.py:33``). The
directory reports them; it never reasons about what a role means.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Optional

from ugence_governance_contracts.api import Validity, ValidityStatus

from ._canon import (
    domain_digest,
    from_iso,
    iso,
    optional_text,
    require_nonempty,
    require_tzaware,
)
from .errors import ContractViolation, RecordIntegrityError
from .principals import PrincipalRef, require_scope

__all__ = ["RoleGrant", "GrantEvent", "GrantEventType", "GRANT_ID_PREFIX", "grant_id_for",
           "validity_to_dict", "validity_from_dict"]

GRANT_ID_PREFIX = "grant_"


def validity_to_dict(validity: Validity) -> dict:
    return {"issued_at": iso(validity.issued_at, "Validity.issued_at"),
            "expires_at": iso(validity.expires_at, "Validity.expires_at") if validity.expires_at else "",
            "stale_after": iso(validity.stale_after, "Validity.stale_after") if validity.stale_after else ""}


def validity_from_dict(d: Optional[dict]) -> Optional[Validity]:
    if not d:
        return None
    return Validity(issued_at=from_iso(d["issued_at"]),
                    expires_at=from_iso(d["expires_at"]) if d.get("expires_at") else None,
                    stale_after=from_iso(d["stale_after"]) if d.get("stale_after") else None)


def grant_id_for(tenant_id: str, principal_id: str, role: str, scope: str,
                 validity: Validity) -> str:
    """Deterministic grant id: no UUID, no clock.

    Two loads of the same grant for the same window are the same grant, so replaying
    an administrator's file does not multiply it.
    """

    return GRANT_ID_PREFIX + domain_digest("grant_id", {
        "tenant_id": require_nonempty(tenant_id, "tenant_id"),
        "principal_id": require_nonempty(principal_id, "principal_id"),
        "role": require_nonempty(role, "role"),
        "scope": require_scope(scope, "scope"),
        "validity": validity_to_dict(validity),
    })[:32]


@dataclass(frozen=True)
class RoleGrant:
    """One principal holds one role, in one scope, for one bounded window."""

    grant_id: str
    tenant_id: str
    principal: PrincipalRef
    role: str
    scope: str
    validity: Validity
    #: A non-secret reference to the basis of the grant (a directory handle, a
    #: policy reference). Never a credential, key or token.
    authority_reference: str = ""
    granting_policy_ref: str = ""
    #: Set on a delegated grant: the delegator's grant id and principal.
    delegation_ref: str = ""
    delegated_from: str = ""
    #: Set on a committee member's grant: the committee principal it is a
    #: membership in. Membership is recorded as an ordinary grant (D-4), so a
    #: member whose grant lapses simply stops being reported.
    member_of: str = ""
    #: Forward-only. From this instant the grant is absent from every answer.
    revoked_at: Optional[datetime] = None
    revocation_reason: str = ""
    loaded_by: str = ""

    def __post_init__(self) -> None:
        for name in ("grant_id", "tenant_id", "role"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), f"RoleGrant.{name}"))
        object.__setattr__(self, "scope", require_scope(self.scope, "RoleGrant.scope"))
        for name in ("authority_reference", "granting_policy_ref", "delegation_ref",
                     "delegated_from", "member_of", "revocation_reason", "loaded_by"):
            object.__setattr__(self, name, optional_text(getattr(self, name), f"RoleGrant.{name}"))
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("RoleGrant.principal must be a PrincipalRef")
        if not isinstance(self.validity, Validity):
            raise ContractViolation(
                "RoleGrant.validity must be a governance-contracts Validity")
        if self.revoked_at is not None:
            require_tzaware(self.revoked_at, "RoleGrant.revoked_at")
        if bool(self.delegation_ref) != bool(self.delegated_from):
            raise ContractViolation(
                "a delegated grant needs both delegation_ref and delegated_from")

    # ------------------------------------------------------------------ #
    @property
    def is_delegated(self) -> bool:
        return bool(self.delegation_ref)

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    def status_at(self, as_of: datetime) -> ValidityStatus:
        return self.validity.status_at(require_tzaware(as_of, "as_of"))

    def is_revoked_at(self, as_of: datetime) -> bool:
        return self.revoked_at is not None and require_tzaware(as_of, "as_of") >= self.revoked_at

    def is_valid_at(self, as_of: datetime) -> bool:
        """Inside its window and not yet revoked. Anything else is absent, not flagged."""

        if self.is_revoked_at(as_of):
            return False
        return self.status_at(as_of) in (ValidityStatus.FRESH, ValidityStatus.STALE)

    def covers(self, scope: str) -> bool:
        from .principals import scope_covers

        return scope_covers(self.scope, scope)

    def revoked(self, *, as_of: datetime, reason: str = "") -> "RoleGrant":
        """A new snapshot; revocation is forward-only and never undone."""

        require_tzaware(as_of, "revoke.as_of")
        if self.revoked_at is not None:
            raise ContractViolation(f"grant '{self.grant_id}' is already revoked")
        return replace(self, revoked_at=as_of,
                       revocation_reason=optional_text(reason, "reason"))

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "grant_id": self.grant_id, "tenant_id": self.tenant_id,
            "principal": self.principal.to_dict(), "role": self.role, "scope": self.scope,
            "validity": validity_to_dict(self.validity),
            "authority_reference": self.authority_reference,
            "granting_policy_ref": self.granting_policy_ref,
            "delegation_ref": self.delegation_ref, "delegated_from": self.delegated_from,
            "member_of": self.member_of,
            "revoked_at": iso(self.revoked_at, "revoked_at") if self.revoked_at else "",
            "revocation_reason": self.revocation_reason, "loaded_by": self.loaded_by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoleGrant":
        return cls(
            grant_id=d["grant_id"], tenant_id=d["tenant_id"],
            principal=PrincipalRef.from_dict(d["principal"]), role=d["role"], scope=d["scope"],
            validity=validity_from_dict(d["validity"]),
            authority_reference=d.get("authority_reference", ""),
            granting_policy_ref=d.get("granting_policy_ref", ""),
            delegation_ref=d.get("delegation_ref", ""), delegated_from=d.get("delegated_from", ""),
            member_of=d.get("member_of", ""),
            revoked_at=from_iso(d["revoked_at"]) if d.get("revoked_at") else None,
            revocation_reason=d.get("revocation_reason", ""), loaded_by=d.get("loaded_by", ""))

    def record_digest(self) -> str:
        return domain_digest("grant", self.to_dict())

    def verify(self, expected_digest: str) -> None:
        if self.record_digest() != expected_digest:
            raise RecordIntegrityError(
                f"grant '{self.grant_id}' does not re-derive its stored record digest")


class GrantEventType(str, Enum):
    """What happened to a grant. The ledger records loading and revocation only —
    a grant is never edited in place."""

    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class GrantEvent:
    """One append-only ledger event. ``sequence`` is monotonic per grant."""

    event_id: str
    grant_id: str
    sequence: int
    event_type: GrantEventType
    occurred_at: datetime
    actor: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "grant_id": self.grant_id,
                "sequence": self.sequence, "event_type": self.event_type.value,
                "occurred_at": iso(self.occurred_at, "occurred_at"),
                "actor": self.actor, "detail": self.detail}
