"""Canonical cost evidence — normalized, time-bounded, supplied cost inputs.

Cost is an *optimization input*, never an authorization mechanism. Phase 3 compares the
estimated cost of feasible candidates using ONLY canonical cost evidence supplied as input;
it performs no provider price lookup, holds no pricing credential, and opens no network
connection.

Money is represented EXACTLY as integer minor units (cents, etc.) plus an ISO-style
currency code, mirroring the Phase-1 ``Unit.CURRENCY_MINOR`` convention — never a float, so
cost arithmetic is exact and free of representation error. A :class:`CostEvidence` names one
resource/subject, a per-unit price on a stated :class:`CostBasis`, an effective interval,
and an evidence source; a :class:`CostBook` gathers cost evidence for one tenant/scope with
a stable content digest.

Fail-closed rejection / abstention rules (some enforced here at construction, the rest by
the recommendation pipeline that consumes this evidence):
  * negative or non-finite amounts are rejected at construction;
  * incompatible pricing bases across compared resources -> pipeline abstains;
  * expired cost evidence (effective interval strictly before the recommendation) ->
    pipeline abstains;
  * unbound tenant/scope -> pipeline abstains;
  * cross-currency comparison without explicit exchange-rate evidence -> pipeline abstains;
  * ambiguous pricing basis -> pipeline abstains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest

COST_EVIDENCE_SCHEMA_VERSION = "capacity-cost-evidence-1"
COST_BOOK_SCHEMA_VERSION = "capacity-cost-book-1"


class CostError(ValueError):
    """Raised when cost evidence is malformed (fail closed)."""


class CostBasis(str, Enum):
    """The unit a cost amount is priced against (its pricing basis / cost basis)."""

    PER_REPLICA_HOUR = "per_replica_hour"       # cost per replica per hour
    PER_CONNECTION_HOUR = "per_connection_hour"  # cost per pool connection per hour
    PER_UNIT_HOUR = "per_unit_hour"             # generic cost per capacity unit per hour


@dataclass(frozen=True)
class Money:
    """Exact money: integer minor units + ISO-style currency code. Immutable."""

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise CostError("amount_minor must be an integer number of minor units")
        if not isinstance(self.currency, str) or len(self.currency) != 3 or not self.currency.isalpha():
            raise CostError("currency must be a 3-letter alphabetic code")
        object.__setattr__(self, "currency", self.currency.upper())

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {"amount_minor": int(self.amount_minor), "currency": self.currency}

    @classmethod
    def from_dict(cls, data: Any) -> "Money":
        if not isinstance(data, Mapping):
            raise CostError("money must be a mapping")
        unknown = set(data) - {"amount_minor", "currency"}
        if unknown:
            raise CostError(f"unknown money field(s): {sorted(unknown)}")
        if "amount_minor" not in data or "currency" not in data:
            raise CostError("money requires 'amount_minor' and 'currency'")
        return cls(amount_minor=data["amount_minor"], currency=data["currency"])


@dataclass(frozen=True)
class CostEvidence:
    """Normalized, time-bounded, supplied per-unit cost for one resource/subject."""

    subject: CapacitySubject
    unit_price: Money
    basis: CostBasis
    effective_from: datetime
    effective_until: datetime
    evidence_source: Optional[str] = None
    schema_version: str = COST_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.subject, CapacitySubject):
            raise CostError("cost subject must be a CapacitySubject")
        if not isinstance(self.unit_price, Money):
            raise CostError("unit_price must be a Money")
        if self.unit_price.amount_minor < 0:
            raise CostError("unit_price must be >= 0 (negative cost is not admissible)")
        if not isinstance(self.basis, CostBasis):
            raise CostError("basis must be a CostBasis")
        if not isinstance(self.effective_from, datetime) or not isinstance(self.effective_until, datetime):
            raise CostError("effective_from/effective_until must be datetimes")
        if self.effective_until < self.effective_from:
            raise CostError("effective_until must be >= effective_from")
        if self.evidence_source is not None and (
            not isinstance(self.evidence_source, str) or self.evidence_source == ""
        ):
            raise CostError("evidence_source must be a non-empty string or None")

    @property
    def currency(self) -> str:
        return self.unit_price.currency

    def is_effective_at(self, when: datetime) -> bool:
        """True iff ``when`` lies within [effective_from, effective_until]."""
        from ..forecasting.series import _as_utc
        w = _as_utc(when)
        return _as_utc(self.effective_from) <= w <= _as_utc(self.effective_until)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "unit_price": self.unit_price.to_canonical_dict(),
            "basis": self.basis.value,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "evidence_source": self.evidence_source,
        }

    def digest(self) -> str:
        return content_digest("capacity_cost_evidence", self.schema_version, self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "CostEvidence":
        if not isinstance(data, Mapping):
            raise CostError("cost evidence must be a mapping")
        known = {"schema_version", "subject", "unit_price", "basis",
                 "effective_from", "effective_until", "evidence_source"}
        unknown = set(data) - known
        if unknown:
            raise CostError(f"unknown cost evidence field(s): {sorted(unknown)}")
        for req in ("subject", "unit_price", "basis", "effective_from", "effective_until"):
            if req not in data:
                raise CostError(f"cost evidence requires '{req}'")
        if not isinstance(data["effective_from"], datetime) or not isinstance(data["effective_until"], datetime):
            raise CostError("effective_from/effective_until must be datetimes")
        try:
            basis = CostBasis(data["basis"])
        except ValueError as exc:
            raise CostError(f"unsupported cost basis: {data['basis']!r}") from exc
        return cls(
            subject=CapacitySubject.from_dict(data["subject"]),
            unit_price=Money.from_dict(data["unit_price"]),
            basis=basis,
            effective_from=data["effective_from"],
            effective_until=data["effective_until"],
            evidence_source=data.get("evidence_source"),
            schema_version=data.get("schema_version", COST_EVIDENCE_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class CostBook:
    """Immutable, tenant/scope-bound collection of cost evidence, keyed by subject."""

    subject: CapacitySubject
    entries: Tuple[CostEvidence, ...] = ()
    schema_version: str = COST_BOOK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.subject, CapacitySubject):
            raise CostError("cost book subject must be a CapacitySubject")
        if not isinstance(self.entries, tuple):
            object.__setattr__(self, "entries", tuple(self.entries))
        from .topology import _subject_scope_compatible
        seen = set()
        for entry in self.entries:
            if not isinstance(entry, CostEvidence):
                raise CostError("every cost book entry must be a CostEvidence")
            if not _subject_scope_compatible(entry.subject, self.subject):
                raise CostError("cross-tenant/scope cost evidence in cost book")
            key = tuple(sorted(entry.subject.to_canonical_dict().items()))
            if key in seen:
                raise CostError("duplicate cost evidence for the same subject")
            seen.add(key)

    def for_subject(self, subject: CapacitySubject) -> Optional[CostEvidence]:
        """Return the cost evidence whose subject matches ``subject`` exactly (or None)."""
        for entry in self.entries:
            if entry.subject == subject:
                return entry
        return None

    def to_canonical_dict(self) -> Dict[str, Any]:
        entry_dicts = [e.to_canonical_dict() for e in self.entries]
        entry_dicts.sort(key=lambda d: str(d["subject"]))
        return {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "entries": entry_dicts,
        }

    def digest(self) -> str:
        return content_digest("capacity_cost_book", self.schema_version, self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "CostBook":
        if not isinstance(data, Mapping):
            raise CostError("cost book must be a mapping")
        known = {"schema_version", "subject", "entries"}
        unknown = set(data) - known
        if unknown:
            raise CostError(f"unknown cost book field(s): {sorted(unknown)}")
        if "subject" not in data:
            raise CostError("cost book requires 'subject'")
        entries_raw = data.get("entries") or ()
        if not isinstance(entries_raw, (list, tuple)):
            raise CostError("entries must be a list")
        return cls(
            subject=CapacitySubject.from_dict(data["subject"]),
            entries=tuple(CostEvidence.from_dict(e) for e in entries_raw),
            schema_version=data.get("schema_version", COST_BOOK_SCHEMA_VERSION),
        )


__all__ = [
    "COST_EVIDENCE_SCHEMA_VERSION",
    "COST_BOOK_SCHEMA_VERSION",
    "CostError",
    "CostBasis",
    "Money",
    "CostEvidence",
    "CostBook",
]
