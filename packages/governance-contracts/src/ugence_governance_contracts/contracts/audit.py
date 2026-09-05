"""Neutral audit reference — *where is the audit entry for this?* (G4).

Closes the **contract half** of gap **G4** of the governance-contracts evolution
plan (``Project_documentation/repository/docs/migrations/governance_contracts/
CONTRACT_GAPS_AND_EVOLUTION_PLAN.md:42-48``): audit shapes are fragmented across
the platform and nothing neutral lets one governance record point at the audit
entry that explains it, so cross-capability audit correlation had no vocabulary.

The gap statement named three shapes. There are now more: the kernel's
``AuditRepository`` port, a durable hash-linked log in storygraph, and separate
append-only event tables in policy-authority, risk_authority, execution-reservation,
approval-workflow and authority-directory. **This contract does not unify them.**
It gives them one way to be *pointed at*, so a consumer can correlate entries
across stores without any store changing, moving, or merging. Anything more is a
migration this contract deliberately does not attempt.

This module defines **contracts and structural invariants only**. It is not an
audit log, a sink, a hash chain, an event catalog, a verifier or an authority. It
grants no permission and mints no authority: an :class:`AuditReference` says where
an entry lives and what it digested to, and nothing about whether the entry is
true, complete, or was ever written by anyone entitled to write it.

What a reference carries, and why
---------------------------------
``store_ref`` names *which* audit store — the fragmentation is real and a
reference that hid it would be unusable for correlation. ``entry_ref`` locates the
entry within that store, and ``entry_digest`` binds its content, so a reference
cannot silently follow an entry that changed. ``correlation_id`` is the optional
thread a caller already uses to tie a request chain together.

A reference carries **no identity of its own**. It is a value, not an entity:
``(tenant_id, store_ref, entry_ref)`` is the location and
:meth:`AuditReference.canonical_digest` is the handle. A synthetic reference id
would be minted independently by each producer, so two records citing the same
entry would digest differently for no reason a consumer could act on — which is
exactly the correlation this contract exists to make possible.

What it deliberately does **not** carry
---------------------------------------
* the entry **body** — a reference that embedded the record would be a second copy
  of the audit, which is the fragmentation G4 describes, not a fix for it;
* an **event-type vocabulary** — Decision Authority's ``AuditEventType`` is frozen
  at 1.0.0 and owns its names; a neutral second catalog would fork them;
* a **chain head or previous-entry hash** — hash-linking is each store's own
  property, and requiring it here would oblige every store to change.

Instants
--------
``recorded_at`` is optional and, when present, must be timezone-aware; a naive
datetime names no instant and is rejected rather than assumed to be UTC.
Canonicalization re-expresses it in UTC before the package's sorted-key JSON
serialization, exactly as :class:`~ugence_governance_contracts.contracts.validity.Validity`
and ``AssessedSystemBinding`` do, so two equal references written with different
offsets share one digest. The system clock is never read.

Relation to the frozen provider contracts
-----------------------------------------
The provider dataclasses are **unchanged**. A consumer that adopts this contract
carries an :class:`AuditReference` *alongside* a result; no existing field, default,
constructor signature or serialized form moves.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

__all__ = [
    "AuditContractError",
    "AuditReference",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AuditContractError(ValueError):
    """A structurally invalid audit reference. Always a refusal, never a warning."""


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring system_identity.py)
# --------------------------------------------------------------------------- #
def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise AuditContractError(f"{name} must be a string (got {type(value).__name__})")
    return value.strip()


def _require_nonempty(value: object, name: str) -> str:
    text = _require_str(value, name)
    if not text:
        raise AuditContractError(f"{name} must be a non-empty string")
    return text


def _validate_digest(value: object, name: str) -> str:
    text = _require_nonempty(value, name)
    if not _SHA256_RE.match(text):
        raise AuditContractError(f"{name} must be a lowercase 64-char sha-256 hex digest")
    return text


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise AuditContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise AuditContractError(f"{name} must be timezone-aware")
    return value


def _to_utc(value: datetime, name: str) -> datetime:
    """Re-express an aware instant in UTC with an **explicit** target.

    The zero-argument form, which infers the local timezone, is deliberately
    never used.
    """

    return _require_tzaware(value, name).astimezone(timezone.utc)


def _canonical_bytes(obj) -> bytes:
    payload = dataclasses.asdict(obj)
    owner = type(obj).__name__
    for name, value in payload.items():
        if isinstance(value, datetime):
            payload[name] = _to_utc(value, f"{owner}.{name}")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return encoded.encode("utf-8")


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AuditReference:
    """An immutable, digest-bound pointer to one entry in one audit store.

    Every field participates in :meth:`canonical_digest`, so the complete
    reference — not merely the entry it names — distinguishes one from another. The
    dataclass is frozen, so no post-construction mutation can alter the content
    or the digest.

    It answers *where the audit entry is*, never *what it says*: dereferencing is
    the store's job, and interpreting the entry is its owner's.
    """

    tenant_id: str
    #: Which audit store holds the entry. Named, never hidden: the platform's
    #: audit stores are separate, and a reference that concealed which one it
    #: pointed at could not be dereferenced.
    store_ref: str
    #: Where the entry sits within that store (a sequence number, event id, row
    #: key — the store's own spelling, uninterpreted here).
    entry_ref: str
    #: The entry's content digest, so a reference cannot silently follow an entry
    #: that changed.
    entry_digest: str
    correlation_id: str = ""
    recorded_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        for name in ("tenant_id", "store_ref", "entry_ref"):
            object.__setattr__(self, name, _require_nonempty(getattr(self, name),
                                                             f"AuditReference.{name}"))
        object.__setattr__(self, "entry_digest",
                           _validate_digest(self.entry_digest, "AuditReference.entry_digest"))
        object.__setattr__(self, "correlation_id",
                           _require_str(self.correlation_id, "AuditReference.correlation_id"))
        if self.recorded_at is not None:
            _require_tzaware(self.recorded_at, "AuditReference.recorded_at")

    # ------------------------------------------------------------------ #
    def canonical_bytes(self) -> bytes:
        """Deterministic canonical JSON bytes over the UTC-normalized payload."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over :meth:`canonical_bytes`.

        Equal references — including ones written with different offsets — share
        one digest; any differing field changes it.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    # ------------------------------------------------------------------ #
    def points_to_same_entry(self, other: "AuditReference") -> bool:
        """Whether two references name the same entry in the same store.

        Compares the *location* (tenant, store, entry), not the digest: two
        references that disagree on ``entry_digest`` still point at one entry, and
        that disagreement is exactly what a consumer needs to detect.
        """

        if not isinstance(other, AuditReference):
            raise AuditContractError("points_to_same_entry.other must be an AuditReference")
        return (self.tenant_id, self.store_ref, self.entry_ref) == (
            other.tenant_id, other.store_ref, other.entry_ref)

    def agrees_with(self, other: "AuditReference") -> bool:
        """Same entry **and** the same content digest for it."""

        return self.points_to_same_entry(other) and self.entry_digest == other.entry_digest
