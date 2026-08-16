"""The policy registry seam and its in-memory reference implementation (§9).

**Reference-grade, not production persistence.** :class:`InMemoryPolicyRegistry`
exists so the issuance and resolution semantics are executable and testable end
to end. It is not a database, has no durability, no replication, no concurrency
control beyond a process-local structure, and no operational story. A
production registry implements :class:`PolicyRegistry` against real storage.

Semantics the interface guarantees, and the reference implementation proves:

* **exact resolution only** — a lookup takes a complete
  :class:`PolicyReference` (id + family + version + content digest + scope +
  tenant). There is deliberately **no** ``latest()``, ``current()`` or
  ``find_by_id()`` method: a floating reference is unrepresentable in the
  trusted evaluation path, not merely discouraged;
* **append-only** — an issued version is never overwritten or deleted;
* **idempotent identical re-submission** — resubmitting a canonically identical
  record is a no-op that returns the stored record;
* **conflict rejection** — reusing an identity/version slot with any different
  content raises :class:`PolicyRegistryConflictError`;
* **no cross-tenant leakage** — a lookup for the wrong tenant is a typed
  not-found; it never reveals that a record exists under another tenant;
* **lookup is not validity** — the registry performs *no* trust checks. It
  returns what was stored. Only :func:`resolve_policy` decides validity.

``issued_records_for_identity`` exists solely to feed the *deny-side*
supersession rule. It returns every version of an identity and never selects
one, so it cannot be used to resolve a floating reference; resolution never
calls it to choose an artifact.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyReference, PolicyScope

from .canonical import canonical_bytes
from .errors import PolicyRegistryConflictError
from .records import IssuedPolicyRecord, PolicyRevocationRecord

__all__ = ["PolicyRegistry", "InMemoryPolicyRegistry"]


def _record_identity_bytes(record: IssuedPolicyRecord) -> bytes:
    """Canonical bytes of a record, used for byte-for-byte idempotence."""

    return canonical_bytes(record)


@runtime_checkable
class PolicyRegistry(Protocol):
    """Narrow storage seam for issued policy versions and their revocations."""

    def append_issuance(self, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        """Append an issuance record; idempotent iff canonically identical."""
        ...

    def get_issued(self, reference: PolicyReference) -> Optional[IssuedPolicyRecord]:
        """Return the record stored under this *exact* reference, or ``None``."""
        ...

    def issued_records_for_identity(
        self,
        *,
        policy_id: str,
        policy_family: PolicyFamily,
        scope: PolicyScope,
        tenant_id: str,
    ) -> tuple[IssuedPolicyRecord, ...]:
        """Every issued version of one identity. Never selects one."""
        ...

    def append_revocation(self, record: PolicyRevocationRecord) -> PolicyRevocationRecord:
        """Append a policy-version revocation; idempotent iff identical."""
        ...

    def revocations_for(self, reference: PolicyReference) -> tuple[PolicyRevocationRecord, ...]:
        """Revocations targeting this *exact* reference."""
        ...


class InMemoryPolicyRegistry:
    """Process-local, append-only reference registry. Not for production use."""

    def __init__(self) -> None:
        self._issued: dict[PolicyReference, IssuedPolicyRecord] = {}
        self._issued_bytes: dict[PolicyReference, bytes] = {}
        self._identity_slots: dict[tuple, PolicyReference] = {}
        self._revocations: dict[PolicyReference, PolicyRevocationRecord] = {}
        self._revocation_bytes: dict[PolicyReference, bytes] = {}

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------
    def append_issuance(self, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        if not isinstance(record, IssuedPolicyRecord):
            raise PolicyRegistryConflictError("append_issuance requires an IssuedPolicyRecord")

        reference = record.policy_reference
        encoded = _record_identity_bytes(record)

        existing = self._issued.get(reference)
        if existing is not None:
            if self._issued_bytes[reference] == encoded:
                # Byte-for-byte identical re-submission: idempotent no-op.
                return existing
            raise PolicyRegistryConflictError(
                f"an issuance record already exists for {reference.policy_id}@"
                f"{reference.version} with different content; issued versions are "
                "immutable and cannot be overwritten"
            )

        slot = record.identity_key
        claimed_by = self._identity_slots.get(slot)
        if claimed_by is not None and claimed_by != reference:
            raise PolicyRegistryConflictError(
                f"policy {reference.policy_id!r} version {reference.version!r} is already "
                f"issued with content digest {claimed_by.content_digest}; a version "
                "identity cannot be reused for different content"
            )

        self._issued[reference] = record
        self._issued_bytes[reference] = encoded
        self._identity_slots[slot] = reference
        return record

    def get_issued(self, reference: PolicyReference) -> Optional[IssuedPolicyRecord]:
        if not isinstance(reference, PolicyReference):
            return None
        # Exact-key lookup. A reference differing in any component — including
        # tenant — simply misses, so a cross-tenant probe is indistinguishable
        # from a nonexistent policy and leaks nothing.
        return self._issued.get(reference)

    def issued_records_for_identity(
        self,
        *,
        policy_id: str,
        policy_family: PolicyFamily,
        scope: PolicyScope,
        tenant_id: str,
    ) -> tuple[IssuedPolicyRecord, ...]:
        matches = [
            record
            for reference, record in self._issued.items()
            if reference.policy_id == policy_id
            and reference.policy_family is policy_family
            and reference.scope is scope
            and reference.tenant_id == tenant_id
        ]
        # Sorted by the record's own identity, never by insertion order, so the
        # result cannot depend on the order in which versions were registered.
        return tuple(
            sorted(matches, key=lambda r: (r.policy_reference.version, r.record_id))
        )

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------
    def append_revocation(self, record: PolicyRevocationRecord) -> PolicyRevocationRecord:
        if not isinstance(record, PolicyRevocationRecord):
            raise PolicyRegistryConflictError(
                "append_revocation requires a PolicyRevocationRecord"
            )

        reference = record.policy_reference
        encoded = canonical_bytes(record)

        existing = self._revocations.get(reference)
        if existing is not None:
            if self._revocation_bytes[reference] == encoded:
                return existing
            raise PolicyRegistryConflictError(
                f"a different revocation record already targets {reference.policy_id}@"
                f"{reference.version}; conflicting revocations are rejected"
            )

        self._revocations[reference] = record
        self._revocation_bytes[reference] = encoded
        return record

    def revocations_for(self, reference: PolicyReference) -> tuple[PolicyRevocationRecord, ...]:
        if not isinstance(reference, PolicyReference):
            return ()
        record = self._revocations.get(reference)
        return (record,) if record is not None else ()
