"""The policy registry seam and its in-memory reference implementation (ADR §15).

**Reference-grade and process-local, not production persistence.**
:class:`InMemoryPolicyRegistry` exists so the issuance and resolution semantics
are executable and testable end to end. It has no durability, no replication,
no cross-process visibility, and no operational story. Production persistence
and distributed concurrency are deferred (ADR §15.7).

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
from .errors import PolicyRegistryConflictError
from .records import IssuedPolicyRecord, PolicyRevocationRecord

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


class InMemoryPolicyRegistry:
    """Process-local, append-only, lock-guarded reference registry.

    Not for production use. See the module docstring for the exact scope of the
    atomicity guarantee.
    """

    def __init__(self) -> None:
        # Re-entrant so a compound operation may call a guarded read.
        self._lock = threading.RLock()
        self._issued: dict[PolicyCoordinate, IssuedPolicyRecord] = {}
        self._issued_bytes: dict[PolicyCoordinate, bytes] = {}
        self._identity_slots: dict[tuple, PolicyCoordinate] = {}
        self._revocations: dict[PolicyCoordinate, PolicyRevocationRecord] = {}
        self._revocation_bytes: dict[PolicyCoordinate, bytes] = {}

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
