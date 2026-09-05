"""Neutral validity contract — *when is a governance artifact still good?* (G8).

Closes contract gap **G8** of the governance-contracts evolution plan: the
provider families each carried expiry ad hoc (``ActionGovernanceResult.expiry``,
``ActionGovernanceRequest.authorization_expired``) and nothing neutral described
freshness, so every consumer answered "is this still valid?" in its own words.

This module defines **contracts and structural invariants only**. It is not a
clock, a revocation service, an authority or a policy engine. It grants no
permission and mints no authority: a :class:`Validity` says how long an artifact
*claims* to be good for, and nothing about whether the claim was ever true.

Semantics
---------
A validity window is **half-open**: ``[issued_at, expires_at)``. ``issued_at``
is required; ``expires_at`` is optional and ``None`` means the artifact carries
no hard expiry. ``stale_after`` is an optional *soft* bound strictly inside the
window: at or past it the artifact is still valid but **stale** — a consumer
that requires freshness must re-obtain it. The four states are ordered by
precedence, and :meth:`Validity.status_at` returns exactly one of them:

| ``as_of`` position                     | status            |
|----------------------------------------|-------------------|
| before ``issued_at``                   | ``NOT_YET_VALID`` |
| at or after ``expires_at``             | ``EXPIRED``       |
| at or after ``stale_after``            | ``STALE``         |
| otherwise                              | ``FRESH``         |

Staleness is **derived at an explicit instant, never stored**. The evolution plan
sketched a ``stale`` field; a stored boolean would itself go stale the moment it
was written, so the contract carries the bound and derives the answer from a
caller-supplied ``as_of``. The system clock is never read — the same rule the
rest of this package follows.

Instants
--------
Every instant must be timezone-aware; a naive datetime names no instant and is
rejected at construction and again at evaluation, never defaulted to UTC.
Canonicalization re-expresses every aware instant in UTC before the package's
sorted-key JSON serialization, exactly as ``AssessedSystemBinding`` does, so two
equal windows written with different offsets are byte-identical.

Relation to the frozen provider contracts
-----------------------------------------
The provider dataclasses are **unchanged**: their fields, defaults, constructor
signatures and serialized forms are pinned by the serialization-equivalence
tests, and adding a key to their ``asdict`` output would silently move every
fingerprint a consumer computes over an existing request. Consumers that adopt
this contract carry a :class:`Validity` *alongside* a result and map it as
``ActionGovernanceResult.expiry == validity.expires_at`` and
``ActionGovernanceRequest.authorization_expired == not validity.is_valid_at(as_of)``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

__all__ = [
    "ValidityContractError",
    "ValidityStatus",
    "Validity",
]


class ValidityContractError(ValueError):
    """A structural validity invariant was violated.

    Subclasses :class:`ValueError`, mirroring
    :class:`~.evidence.EvidenceContractError`, so existing ``ValueError``
    handling still catches it. It signals a *structural* rejection — never a
    claim that any authority evaluated the artifact.
    """


class ValidityStatus(str, Enum):
    """Exactly one of these describes an artifact at one explicit instant."""

    NOT_YET_VALID = "NOT_YET_VALID"
    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring system_identity.py)
# --------------------------------------------------------------------------- #
def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValidityContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValidityContractError(f"{name} must be timezone-aware")
    return value


def _to_utc(value: datetime, name: str) -> datetime:
    """Re-express an aware instant in UTC; reject a naive one.

    ``astimezone(timezone.utc)`` with an **explicit** target is pure arithmetic
    over the value's own offset. The zero-argument form, which infers the local
    timezone, is deliberately never used.
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


@dataclass(frozen=True)
class Validity:
    """A half-open ``[issued_at, expires_at)`` window with an optional soft bound.

    All three fields are timezone-aware instants or ``None``. The window must be
    non-empty (``issued_at < expires_at`` when both are present) and the soft
    bound, when present, must lie inside it (``issued_at <= stale_after`` and
    ``stale_after < expires_at``). Every field participates in
    :meth:`canonical_digest`.
    """

    issued_at: datetime
    expires_at: Optional[datetime] = None
    stale_after: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_tzaware(self.issued_at, "Validity.issued_at")
        for name in ("expires_at", "stale_after"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"Validity.{name}")
        if self.expires_at is not None and not self.issued_at < self.expires_at:
            raise ValidityContractError(
                "Validity window is half-open [issued_at, expires_at): "
                "issued_at must precede expires_at"
            )
        if self.stale_after is not None:
            if self.stale_after < self.issued_at:
                raise ValidityContractError(
                    "Validity.stale_after must not precede issued_at"
                )
            if self.expires_at is not None and not self.stale_after < self.expires_at:
                raise ValidityContractError(
                    "Validity.stale_after must precede expires_at: an artifact "
                    "cannot become stale only after it has already expired"
                )

    # ------------------------------------------------------------------ #
    # Evaluation at an explicit instant — the clock is never read
    # ------------------------------------------------------------------ #
    def status_at(self, as_of: datetime) -> ValidityStatus:
        """The single :class:`ValidityStatus` that applies at ``as_of``.

        Precedence is ``NOT_YET_VALID``, then ``EXPIRED``, then ``STALE``, then
        ``FRESH``. ``as_of`` must be timezone-aware; a naive value is rejected
        rather than assumed to be UTC.
        """

        _require_tzaware(as_of, "Validity.status_at.as_of")
        if as_of < self.issued_at:
            return ValidityStatus.NOT_YET_VALID
        if self.expires_at is not None and as_of >= self.expires_at:
            return ValidityStatus.EXPIRED
        if self.stale_after is not None and as_of >= self.stale_after:
            return ValidityStatus.STALE
        return ValidityStatus.FRESH

    def is_valid_at(self, as_of: datetime) -> bool:
        """Inside the half-open window: ``FRESH`` or ``STALE``."""

        return self.status_at(as_of) in (ValidityStatus.FRESH, ValidityStatus.STALE)

    def is_fresh_at(self, as_of: datetime) -> bool:
        """Valid **and** not past the soft bound."""

        return self.status_at(as_of) is ValidityStatus.FRESH

    def is_stale_at(self, as_of: datetime) -> bool:
        """Valid but past the soft bound — re-obtain before relying on it."""

        return self.status_at(as_of) is ValidityStatus.STALE

    def is_expired_at(self, as_of: datetime) -> bool:
        """At or past ``expires_at``."""

        return self.status_at(as_of) is ValidityStatus.EXPIRED

    # ------------------------------------------------------------------ #
    # Canonical form
    # ------------------------------------------------------------------ #
    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` hashes, instants in UTC."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over :meth:`canonical_bytes`.

        Equal windows — including ones written with different offsets — share
        one digest; a genuinely different instant changes it.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()
