"""The policy registry seam and its in-memory reference implementation (ADR §15).

**Reference-grade and process-local, not production persistence.**
:class:`InMemoryPolicyRegistry` exists so the issuance and resolution semantics
are executable and testable end to end. It has no durability, no replication,
no cross-process visibility, and no operational story. Production
persistence is :class:`~.registry_sqlite.SqlitePolicyRegistry` (ADR §15.7,
closed under decision D-3); distributed concurrency remains disclaimed.

What it *does* guarantee, and what it deliberately does not:

* **exact coordinate resolution only** — there is no ``latest()``,
  ``current()`` or ``find_by_id()``, so a floating reference is
  *unrepresentable* on the trusted path, not merely discouraged;
* **append-only** issuance and revocation, in separate stores;
* **idempotent** only on a canonically identical resubmission; any other reuse
  of a version slot is a typed conflict;
* **no cross-tenant leakage** — a lookup for the wrong tenant is the same typed
  miss as a nonexistent record and reveals no other tenant's identifiers;
* **process-local atomicity** — compound check-and-append sequences and reads
  needing a consistent view are guarded by a re-entrant lock, so concurrent
  threads in *this process* cannot interleave into a corrupt state. This is
  **not** distributed or durable atomicity and is not claimed to be;
* **lookup is not validity** — the registry performs no trust checks whatsoever.

``issued_records_for_identity`` returns every version of an identity and never
selects one. It exists for administrative enumeration; the trusted resolution
path does not call it.
"""

from __future__ import annotations

import threading
from typing import Optional, Protocol, runtime_checkable

from .adapters import PolicyCoordinate
from .canonical import canonical_bytes
from .consistency import PolicyRegistryConsistencyDescriptor, PolicyRegistryConsistencyScope
from .errors import PolicyRegistryConflictError, PolicyRegistryProductionModeError
from .records import (
    IssuedPolicyRecord,
    PolicyRevocationRecord,
    PolicySupersessionRecord,
)

__all__ = ["PolicyRegistry", "InMemoryPolicyRegistry"]


def _record_bytes(record: object) -> bytes:
    """Canonical bytes of a record, used for byte-for-byte idempotence."""

    from dataclasses import fields

    return canonical_bytes(
        {f.name: getattr(record, f.name) for f in fields(record) if f.name != "policy"}
        | {"policy_body_digest": getattr(record, "policy_body_digest", None)}
    )


@runtime_checkable
class PolicyRegistry(Protocol):
    """Narrow storage seam for issued policy versions and their revocations."""

    def append_issuance(self, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        """Append an issuance record; idempotent iff canonically identical."""
        ...

    def get_issued(self, coordinate: PolicyCoordinate) -> Optional[IssuedPolicyRecord]:
        """Return the record stored under this *exact* coordinate, or ``None``."""
        ...

    def issued_records_for_identity(
        self, *, policy_family: str, policy_id: str, scope: str, tenant_id: str
    ) -> tuple[IssuedPolicyRecord, ...]:
        """Every issued version of one identity. Never selects one."""
        ...

    def append_revocation(self, record: PolicyRevocationRecord) -> PolicyRevocationRecord:
        """Append a policy-version revocation; idempotent iff identical."""
        ...

    def revocations_for(
        self, coordinate: PolicyCoordinate
    ) -> tuple[PolicyRevocationRecord, ...]:
        """Revocations targeting this *exact* coordinate."""
        ...

    def append_issuance_with_supersession(
        self,
        record: IssuedPolicyRecord,
        supersession: PolicySupersessionRecord,
    ) -> tuple[IssuedPolicyRecord, PolicySupersessionRecord]:
        """Append a successor and its supersession as **one** act (`ACC-LC-2`).

        Either both land or neither does. A successor that admitted itself while
        leaving its predecessor resolvable would be two acts wearing one name.
        """
        ...

    def supersessions_for(
        self, coordinate: PolicyCoordinate
    ) -> tuple[PolicySupersessionRecord, ...]:
        """Supersessions naming this *exact* coordinate as the predecessor."""
        ...


class InMemoryPolicyRegistry:
    """Process-local, append-only, lock-guarded reference registry.

    Not for production use. See the module docstring for the exact scope of the
    atomicity guarantee. Asking for ``production_mode=True`` is refused: the
    durable registry is :class:`~.registry_sqlite.SqlitePolicyRegistry`.
    """

    #: Declared consistency: process-local atomicity and read-after-write only.
    consistency = PolicyRegistryConsistencyDescriptor(
        PolicyRegistryConsistencyScope.PROCESS_LOCAL_ONLY
    )

    def __init__(self, *, production_mode: bool = False) -> None:
        if production_mode:
            raise PolicyRegistryProductionModeError(
                "InMemoryPolicyRegistry is the process-local test reference and is refused "
                "in production mode; use SqlitePolicyRegistry on a file path"
            )
        # Re-entrant so a compound operation may call a guarded read.
        self._lock = threading.RLock()
        self._issued: dict[PolicyCoordinate, IssuedPolicyRecord] = {}
        self._issued_bytes: dict[PolicyCoordinate, bytes] = {}
        self._identity_slots: dict[tuple, PolicyCoordinate] = {}
        self._revocations: dict[PolicyCoordinate, PolicyRevocationRecord] = {}
        self._revocation_bytes: dict[PolicyCoordinate, bytes] = {}
        # `ACC-LC-IA-2`: a third append-only store, keyed by the *predecessor*.
        self._supersessions: dict[PolicyCoordinate, PolicySupersessionRecord] = {}
        self._supersession_bytes: dict[PolicyCoordinate, bytes] = {}

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------
    def append_issuance(self, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        if not isinstance(record, IssuedPolicyRecord):
            raise PolicyRegistryConflictError("append_issuance requires an IssuedPolicyRecord")

        coordinate = record.coordinate
        encoded = _record_bytes(record)

        # The whole check-and-append is one critical section: two threads
        # racing the same slot cannot both observe "absent" and both write.
        with self._lock:
            existing = self._issued.get(coordinate)
            if existing is not None:
                if self._issued_bytes[coordinate] == encoded:
                    # Canonically identical resubmission: idempotent no-op.
                    return existing
                raise PolicyRegistryConflictError(
                    f"an issuance record already exists for {coordinate.policy_id}@"
                    f"{coordinate.version} with different content; issued versions are "
                    "immutable and cannot be overwritten"
                )

            slot = coordinate.identity_slot
            claimed_by = self._identity_slots.get(slot)
            if claimed_by is not None and claimed_by != coordinate:
                raise PolicyRegistryConflictError(
                    f"policy {coordinate.policy_id!r} version {coordinate.version!r} is "
                    "already issued with different content; a version identity cannot be "
                    "reused"
                )

            self._issued[coordinate] = record
            self._issued_bytes[coordinate] = encoded
            self._identity_slots[slot] = coordinate
            return record

    def get_issued(self, coordinate: PolicyCoordinate) -> Optional[IssuedPolicyRecord]:
        if not isinstance(coordinate, PolicyCoordinate):
            return None
        # Exact-key lookup. A coordinate differing in any component — including
        # tenant — simply misses, so a cross-tenant probe is indistinguishable
        # from a nonexistent policy and leaks nothing.
        with self._lock:
            return self._issued.get(coordinate)

    def issued_records_for_identity(
        self, *, policy_family: str, policy_id: str, scope: str, tenant_id: str
    ) -> tuple[IssuedPolicyRecord, ...]:
        with self._lock:
            matches = [
                record
                for coordinate, record in self._issued.items()
                if coordinate.policy_family == policy_family
                and coordinate.policy_id == policy_id
                and coordinate.scope == scope
                and coordinate.tenant_id == tenant_id
            ]
        # Sorted by identity, never by insertion order, so the result cannot
        # depend on the order in which versions were registered.
        return tuple(sorted(matches, key=lambda r: (r.coordinate.version, r.record_id)))

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------
    def append_revocation(self, record: PolicyRevocationRecord) -> PolicyRevocationRecord:
        if not isinstance(record, PolicyRevocationRecord):
            raise PolicyRegistryConflictError(
                "append_revocation requires a PolicyRevocationRecord"
            )

        coordinate = record.coordinate
        encoded = canonical_bytes(record)

        with self._lock:
            existing = self._revocations.get(coordinate)
            if existing is not None:
                if self._revocation_bytes[coordinate] == encoded:
                    return existing
                raise PolicyRegistryConflictError(
                    f"a different revocation record already targets {coordinate.policy_id}@"
                    f"{coordinate.version}; conflicting revocations are rejected"
                )
            self._revocations[coordinate] = record
            self._revocation_bytes[coordinate] = encoded
            return record

    def revocations_for(
        self, coordinate: PolicyCoordinate
    ) -> tuple[PolicyRevocationRecord, ...]:
        if not isinstance(coordinate, PolicyCoordinate):
            return ()
        with self._lock:
            record = self._revocations.get(coordinate)
        return (record,) if record is not None else ()

    # ------------------------------------------------------------------
    # Supersession (`ACC-LC-IA-2`)
    # ------------------------------------------------------------------
    def append_issuance_with_supersession(
        self,
        record: IssuedPolicyRecord,
        supersession: PolicySupersessionRecord,
    ) -> tuple[IssuedPolicyRecord, PolicySupersessionRecord]:
        """Append the successor and its supersession under one lock acquisition.

        The lock is re-entrant, so this reuses :meth:`append_issuance` rather
        than duplicating its conflict rules. If the issuance append raises, the
        supersession is never written; if the supersession append raises, the
        issuance is rolled back, because a stored successor whose predecessor
        still resolves is exactly the state this act exists to prevent.
        """

        if not isinstance(supersession, PolicySupersessionRecord):
            raise PolicyRegistryConflictError(
                "append_issuance_with_supersession requires a PolicySupersessionRecord"
            )
        if supersession.successor_coordinate != record.coordinate:
            raise PolicyRegistryConflictError(
                "the supersession record's successor must be the record being issued"
            )

        with self._lock:
            had_issuance = record.coordinate in self._issued
            issued = self.append_issuance(record)
            try:
                stored = self.append_supersession(supersession)
            except Exception:
                if not had_issuance:
                    self._issued.pop(record.coordinate, None)
                    self._issued_bytes.pop(record.coordinate, None)
                    slot = record.coordinate.identity_slot
                    if self._identity_slots.get(slot) == record.coordinate:
                        self._identity_slots.pop(slot, None)
                raise
            return issued, stored

    def append_supersession(
        self, record: PolicySupersessionRecord
    ) -> PolicySupersessionRecord:
        if not isinstance(record, PolicySupersessionRecord):
            raise PolicyRegistryConflictError(
                "append_supersession requires a PolicySupersessionRecord"
            )

        coordinate = record.coordinate
        encoded = canonical_bytes(record)

        with self._lock:
            existing = self._supersessions.get(coordinate)
            if existing is not None:
                if self._supersession_bytes[coordinate] == encoded:
                    return existing
                raise PolicyRegistryConflictError(
                    f"a different supersession record already targets "
                    f"{coordinate.policy_id}@{coordinate.version}; a version cannot be "
                    "superseded twice by different successors"
                )
            self._supersessions[coordinate] = record
            self._supersession_bytes[coordinate] = encoded
            return record

    def supersessions_for(
        self, coordinate: PolicyCoordinate
    ) -> tuple[PolicySupersessionRecord, ...]:
        if not isinstance(coordinate, PolicyCoordinate):
            return ()
        with self._lock:
            record = self._supersessions.get(coordinate)
        return (record,) if record is not None else ()
