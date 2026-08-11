"""Persisted authoritative authority state (RA-6 §4) — reference adapter.

The single authoritative source of truth the writer mutates and the edge caches
sync from. It is **strongly-consistent, serialized-per-tenant, and monotonic**:

* ``current_epoch(tenant)`` is a monotonic integer (base 1); it only ever
  advances. A replicated update carrying a *lower* epoch is a no-op — epoch
  rollback is never permitted to revalidate old authority (invariants I3/I14).
* Targeted revocations (envelope / subject / model) form a **grow-only union**:
  a revocation never un-happens, and a duplicate revoke is an idempotent no-op
  (invariant I13).
* ``advance_epoch`` is idempotent under a caller-supplied ``change_id`` so a
  retried command does not double-bump (closes R-2).

This is a **reference / in-memory** persistence adapter: deterministic and
correct for conformance and tests, with production Postgres delegated to
:mod:`.postgres` (which completes the reserved DDL). It is NOT a distributed,
globally-consistent revocation service; see the package README maturity note.

The class is tenant-isolated by construction: every key is ``(tenant, …)``. It
holds a per-tenant lock so concurrent updates to different tenants never block
each other and updates to the same tenant serialize (no lost updates).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set

from risk_authority.services.revocation import RevocationState

__all__ = [
    "BASE_EPOCH",
    "AuthorityStateExport",
    "ReferenceAuthorityStore",
]

# The base epoch every tenant starts at (mirrors the leaf ``RevocationState``
# base without importing its module-private constant).
BASE_EPOCH: int = RevocationState().current_epoch("__base__")


@dataclass(frozen=True)
class AuthorityStateExport:
    """A serializable per-tenant snapshot of authoritative state (for replication).

    Convergence semantics on merge (RA-6 §4.1): ``epoch = max(epoch)``; the three
    revocation sets are grow-only unions. Out-of-order / duplicate exports
    converge safely and can never resurrect revoked authority.
    """

    tenant_id: str
    epoch: int
    revoked_envelopes: frozenset[str] = frozenset()
    revoked_subjects: frozenset[str] = frozenset()
    revoked_models: frozenset[str] = frozenset()


class ReferenceAuthorityStore:
    """In-memory reference implementation of the authoritative authority store."""

    def __init__(self) -> None:
        self._epochs: Dict[str, int] = {}
        self._rev_env: Dict[str, Set[str]] = {}
        self._rev_subj: Dict[str, Set[str]] = {}
        self._rev_model: Dict[str, Set[str]] = {}
        # Idempotency ledger for epoch advancement, per tenant.
        self._epoch_change_ids: Dict[str, Set[str]] = {}
        self._tenants: Set[str] = set()
        self._locks: Dict[str, threading.RLock] = {}
        self._registry_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Locking (per-tenant serialization).                                 #
    # ------------------------------------------------------------------ #
    def _lock_for(self, tenant_id: str) -> threading.RLock:
        with self._registry_lock:
            lock = self._locks.get(tenant_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[tenant_id] = lock
            return lock

    def _touch(self, tenant_id: str) -> None:
        self._tenants.add(tenant_id)
        self._epochs.setdefault(tenant_id, BASE_EPOCH)
        self._rev_env.setdefault(tenant_id, set())
        self._rev_subj.setdefault(tenant_id, set())
        self._rev_model.setdefault(tenant_id, set())
        self._epoch_change_ids.setdefault(tenant_id, set())

    # ------------------------------------------------------------------ #
    # Bootstrap / registry.                                               #
    # ------------------------------------------------------------------ #
    def seed_tenant(self, tenant_id: str) -> None:
        """Seed a tenant at ``epoch=1`` with empty revocation sets (RA-6 §16)."""

        with self._lock_for(tenant_id):
            self._touch(tenant_id)

    def known_tenants(self) -> frozenset[str]:
        with self._registry_lock:
            return frozenset(self._tenants)

    # ------------------------------------------------------------------ #
    # Reads.                                                              #
    # ------------------------------------------------------------------ #
    def current_epoch(self, tenant_id: str) -> int:
        with self._lock_for(tenant_id):
            return self._epochs.get(tenant_id, BASE_EPOCH)

    def build_revocation_state(
        self, tenants: Optional[Iterable[str]] = None
    ) -> RevocationState:
        """Rehydrate a fresh pure :class:`RevocationState` for the given tenants.

        Uses only the leaf's public mutators (``advance_epoch`` / ``revoke_*``)
        so the leaf predicate stays pure and unmodified; the runtime never pokes
        the leaf's private fields.
        """

        target = list(tenants) if tenants is not None else list(self.known_tenants())
        rs = RevocationState()
        for tenant_id in target:
            with self._lock_for(tenant_id):
                epoch = self._epochs.get(tenant_id, BASE_EPOCH)
                for _ in range(epoch - BASE_EPOCH):
                    rs.advance_epoch(tenant_id)
                for env in self._rev_env.get(tenant_id, ()):  # grow-only union
                    rs.revoke_envelope(env)
                for subj in self._rev_subj.get(tenant_id, ()):
                    rs.revoke_subject(tenant_id, subj)
                for model in self._rev_model.get(tenant_id, ()):
                    rs.revoke_model(tenant_id, model)
        return rs

    def export(self, tenant_id: str) -> AuthorityStateExport:
        with self._lock_for(tenant_id):
            self._touch(tenant_id)
            return AuthorityStateExport(
                tenant_id=tenant_id,
                epoch=self._epochs[tenant_id],
                revoked_envelopes=frozenset(self._rev_env[tenant_id]),
                revoked_subjects=frozenset(self._rev_subj[tenant_id]),
                revoked_models=frozenset(self._rev_model[tenant_id]),
            )

    # ------------------------------------------------------------------ #
    # Writes (monotonic, idempotent). Called only by the writer service.  #
    # ------------------------------------------------------------------ #
    def advance_epoch(self, tenant_id: str, change_id: str) -> tuple[int, bool]:
        """Advance the tenant epoch idempotently under ``change_id``.

        Returns ``(epoch, changed)``. A previously-seen ``change_id`` is a no-op
        (``changed=False``) returning the unchanged current epoch (R-2).
        """

        with self._lock_for(tenant_id):
            self._touch(tenant_id)
            if change_id and change_id in self._epoch_change_ids[tenant_id]:
                return self._epochs[tenant_id], False
            self._epochs[tenant_id] += 1
            if change_id:
                self._epoch_change_ids[tenant_id].add(change_id)
            return self._epochs[tenant_id], True

    def revoke_envelope(self, tenant_id: str, envelope_id: str) -> bool:
        return self._add(self._rev_env, tenant_id, envelope_id)

    def revoke_subject(self, tenant_id: str, subject_id: str) -> bool:
        return self._add(self._rev_subj, tenant_id, subject_id)

    def revoke_model(self, tenant_id: str, model_id: str) -> bool:
        return self._add(self._rev_model, tenant_id, model_id)

    def _add(self, bucket: Dict[str, Set[str]], tenant_id: str, target: str) -> bool:
        with self._lock_for(tenant_id):
            self._touch(tenant_id)
            if target in bucket[tenant_id]:
                return False  # idempotent no-op
            bucket[tenant_id].add(target)
            return True

    # ------------------------------------------------------------------ #
    # Replication merge (convergence, RA-6 §4.1).                         #
    # ------------------------------------------------------------------ #
    def merge(self, export: AuthorityStateExport) -> bool:
        """Merge a replicated export: ``max(epoch)`` + grow-only revoke union.

        Returns True iff local state became strictly more restrictive. A lower
        incoming epoch never lowers the local epoch; a duplicate/out-of-order
        export is a safe no-op (invariants I3/I14; no authority resurrection).
        """

        tenant_id = export.tenant_id
        with self._lock_for(tenant_id):
            self._touch(tenant_id)
            changed = False
            if export.epoch > self._epochs[tenant_id]:
                self._epochs[tenant_id] = export.epoch
                changed = True
            for env in export.revoked_envelopes:
                if env not in self._rev_env[tenant_id]:
                    self._rev_env[tenant_id].add(env)
                    changed = True
            for subj in export.revoked_subjects:
                if subj not in self._rev_subj[tenant_id]:
                    self._rev_subj[tenant_id].add(subj)
                    changed = True
            for model in export.revoked_models:
                if model not in self._rev_model[tenant_id]:
                    self._rev_model[tenant_id].add(model)
                    changed = True
            return changed
