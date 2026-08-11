"""Bounded-stale local read cache (RA-6 §4) implementing ``AuthorityStatusReader``.

Each enforcement point holds one of these. It reads a **local snapshot only** —
never a synchronous central call — so the hot path stays offline (RA-6 §4, I12).
The snapshot carries an ``as_of`` timestamp and the set of tenants it has synced;
until the first successful :meth:`sync` it is **UNINITIALIZED** and every read
denies (R-1/I13 — "no state loaded" is never "nothing revoked").

Convergence is delegated to the authoritative store (max-epoch + grow-only
union); the cache is a point-in-time copy plus freshness metadata. A production
deployment feeds :meth:`sync` from event propagation + periodic pull; this
reference cache exposes an explicit :meth:`sync` the caller/scheduler drives.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Iterable, Optional

from risk_authority.services.authority_status import (
    AUTHORITY_STATUS_SCHEMA_VERSION,
    AuthorityStatusSnapshot,
)
from risk_authority.services.revocation import RevocationState

from .store import BASE_EPOCH, ReferenceAuthorityStore

__all__ = ["AuthorityStatusCache"]


class AuthorityStatusCache:
    """A bounded-stale ``AuthorityStatusReader`` fed from an authority store."""

    def __init__(
        self,
        source: ReferenceAuthorityStore,
        *,
        clock: Callable[[], datetime],
        schema_version: str = AUTHORITY_STATUS_SCHEMA_VERSION,
    ) -> None:
        self._source = source
        self._clock = clock
        self._schema_version = schema_version
        self._lock = threading.RLock()
        # UNINITIALIZED until the first successful sync.
        self._state: RevocationState = RevocationState()
        self._as_of: Optional[datetime] = None
        self._tenants: frozenset[str] = frozenset()

    # ------------------------------------------------------------------ #
    # Sync (production: event propagation + periodic pull; here: explicit). #
    # ------------------------------------------------------------------ #
    def sync(self, tenants: Optional[Iterable[str]] = None) -> datetime:
        """Refresh the local snapshot from the authoritative store.

        Records ``as_of = clock()`` on success and marks every synced tenant
        covered. Returns the new ``as_of``.
        """

        target = (
            frozenset(tenants) if tenants is not None else self._source.known_tenants()
        )
        new_state = self._source.build_revocation_state(target)
        now = self._clock()
        with self._lock:
            self._state = new_state
            self._as_of = now
            self._tenants = target
        return now

    # ------------------------------------------------------------------ #
    # AuthorityStatusReader (read-only).                                   #
    # ------------------------------------------------------------------ #
    def snapshot(self, *, tenant_id: str) -> AuthorityStatusSnapshot:
        with self._lock:
            return AuthorityStatusSnapshot(
                revocation_state=self._state,
                as_of=self._as_of,
                tenant_ids=self._tenants,
                schema_version=self._schema_version,
            )

    def current_epoch(self, tenant_id: str) -> int:
        with self._lock:
            if self._as_of is None or tenant_id not in self._tenants:
                # Uninitialized-for-tenant: report the base, but callers MUST use
                # ``is_initialized`` / ``snapshot`` for enforcement (a bare epoch
                # read must never be mistaken for "fresh, nothing revoked").
                return BASE_EPOCH
            return self._state.current_epoch(tenant_id)

    def is_initialized(self, *, tenant_id: str) -> bool:
        with self._lock:
            return self._as_of is not None and tenant_id in self._tenants

    def as_of(self, *, tenant_id: str) -> Optional[datetime]:
        with self._lock:
            if self._as_of is None or tenant_id not in self._tenants:
                return None
            return self._as_of
