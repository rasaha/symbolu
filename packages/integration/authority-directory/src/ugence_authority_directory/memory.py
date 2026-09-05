"""In-memory reference adapter — tests and local composition, refused in production.

Process-local, under one re-entrant lock. It applies the same pure delegation and
selection rules as the SQLite adapter; only storage differs.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime
from typing import Optional

from ._canon import require_nonempty, require_tzaware
from .delegation import delegation_refusals
from .directory import CommitteeReport
from .errors import (
    DelegationRefused,
    GrantAlreadyExistsError,
    GrantNotFoundError,
    ProductionModeRefused,
    StoreUnavailableError,
)
from .grants import GrantEvent, GrantEventType, RoleGrant
from .selection import build_committee_report, select_for_principal, select_holders
from .version import MATURITY

__all__ = ["InMemoryAuthorityDirectory"]


class InMemoryAuthorityDirectory:
    """Reference adapter for :class:`~ugence_authority_directory.directory.AuthorityDirectoryPort`."""

    maturity = MATURITY

    def __init__(self, *, production_mode: bool = False) -> None:
        if production_mode:
            raise ProductionModeRefused(
                "InMemoryAuthorityDirectory is a test reference adapter and is refused in "
                "production mode; use SqliteAuthorityDirectory on a file path")
        self._lock = threading.RLock()
        self._closed = False
        self._grants: dict[str, RoleGrant] = {}
        self._events: dict[str, list[GrantEvent]] = {}

    def close(self) -> None:
        self._closed = True

    def _guard(self) -> None:
        if self._closed:
            raise StoreUnavailableError("store closed")

    def _append(self, grant: RoleGrant, event_type: GrantEventType, occurred_at: datetime,
                actor: str, detail: str = "") -> GrantEvent:
        events = self._events.setdefault(grant.grant_id, [])
        seq = len(events)
        event = GrantEvent(event_id=f"{grant.grant_id}:{seq}", grant_id=grant.grant_id,
                           sequence=seq, event_type=event_type, occurred_at=occurred_at,
                           actor=actor, detail=detail)
        events.append(event)
        return event

    # ------------------------------------------------------------------ #
    # AuthorityDirectoryPort
    # ------------------------------------------------------------------ #
    def put_grant(self, grant: RoleGrant, *, as_of: datetime, loaded_by: str = "") -> RoleGrant:
        require_tzaware(as_of, "put_grant.as_of")
        with self._lock:
            self._guard()
            if grant.grant_id in self._grants:
                raise GrantAlreadyExistsError(
                    f"grant '{grant.grant_id}' already exists; a grant is a record and is "
                    "never overwritten")
            if grant.is_delegated:
                refusals = delegation_refusals(grant, self._grants.get(grant.delegation_ref), as_of)
                if refusals:
                    raise DelegationRefused("; ".join(refusals))
            stored = replace(grant, loaded_by=loaded_by.strip()) if loaded_by else grant
            self._grants[stored.grant_id] = stored
            self._append(stored, GrantEventType.GRANTED, as_of, loaded_by, stored.role)
            return stored

    def revoke_grant(self, grant_id: str, *, as_of: datetime, reason: str = "",
                     actor: str = "") -> RoleGrant:
        with self._lock:
            self._guard()
            grant = self._require(grant_id)
            revoked = grant.revoked(as_of=as_of, reason=reason)
            self._grants[grant_id] = revoked
            self._append(revoked, GrantEventType.REVOKED, as_of, actor, revoked.revocation_reason)
            return revoked

    def _require(self, grant_id: str) -> RoleGrant:
        grant = self._grants.get(require_nonempty(grant_id, "grant_id"))
        if grant is None:
            raise GrantNotFoundError(f"no grant '{grant_id}'")
        return grant

    def get_grant(self, grant_id: str) -> Optional[RoleGrant]:
        with self._lock:
            self._guard()
            return self._grants.get(grant_id)

    def grants_for(self, *, tenant_id: str, principal_id: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]:
        with self._lock:
            self._guard()
            return select_for_principal(self._grants.values(), tenant_id=tenant_id,
                                        principal_id=principal_id, as_of=as_of)

    def holders_of(self, *, tenant_id: str, role: str, scope: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]:
        with self._lock:
            self._guard()
            return select_holders(self._grants.values(), tenant_id=tenant_id, role=role,
                                  scope=scope, as_of=as_of)

    def committee_report(self, *, tenant_id: str, committee_id: str, role: str, scope: str,
                         as_of: datetime) -> Optional[CommitteeReport]:
        with self._lock:
            self._guard()
            return build_committee_report(self._grants.values(), tenant_id=tenant_id,
                                          committee_id=committee_id, role=role, scope=scope,
                                          as_of=as_of)

    def grant_events(self, grant_id: str) -> tuple[GrantEvent, ...]:
        with self._lock:
            self._guard()
            return tuple(self._events.get(grant_id, ()))
