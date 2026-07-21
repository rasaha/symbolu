"""
Provenance model and instruction-precedence resolution (Sections 8 & 10).

Two responsibilities:

1. An append-only provenance ledger. Entries are only ever added; a builder that
   tries to rewrite an existing field's provenance raises. Default assumptions are
   recorded as visible, removable entries (``DEFAULT_ASSUMPTION``) rather than being
   silently folded into explicit fields.

2. Deterministic instruction precedence. Given two competing values with different
   provenance kinds, the one whose kind ranks higher on ``PRECEDENCE_ORDER`` wins.
   This encodes: current explicit > deterministic extraction of it > app metadata /
   referenced artifact > conversation context > stable defaults > model inference.

Nothing here judges truth; it only decides which *source* of an interpretation
takes priority and records where every value came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import (
    AUTHORITATIVE_PROVENANCE, PRECEDENCE_ORDER, Provenance, ProvenanceEntry,
    ProvenanceKind, precedence_rank,
)


class ProvenanceViolation(Exception):
    """Raised when append-only provenance is violated (a field's origin would be
    silently overwritten, or explicit provenance claimed for inferred content)."""


@dataclass
class ProvenanceLedger:
    """Append-only ledger of (field_path, kind, detail). Enforces that a field is
    never re-attributed to a *different* origin once recorded, which is what makes
    "claiming explicit provenance for inferred content" detectable rather than
    silent."""
    _entries: List[ProvenanceEntry] = field(default_factory=list)
    _by_path: Dict[str, ProvenanceKind] = field(default_factory=dict)

    def record(self, field_path: str, kind: ProvenanceKind, detail: str = "") -> None:
        existing = self._by_path.get(field_path)
        if existing is not None and existing != kind:
            # An inferred field must never be re-stamped as explicit (or vice
            # versa). Distinct sub-paths (field_path with an index) avoid this.
            raise ProvenanceViolation(
                f"append-only violation: {field_path!r} already {existing.value}, "
                f"cannot re-record as {kind.value}")
        self._by_path[field_path] = kind
        self._entries.append(ProvenanceEntry(field_path, kind, detail))

    def entries(self) -> Tuple[ProvenanceEntry, ...]:
        return tuple(self._entries)

    def kind_of(self, field_path: str) -> Optional[ProvenanceKind]:
        return self._by_path.get(field_path)

    def default_assumptions(self) -> Tuple[ProvenanceEntry, ...]:
        return tuple(e for e in self._entries
                     if e.kind is ProvenanceKind.DEFAULT_ASSUMPTION)

    def remove_defaults(self) -> "ProvenanceLedger":
        """Default assumptions must be removable (Section 8). Returns a new ledger
        with all DEFAULT_ASSUMPTION entries dropped."""
        kept = [e for e in self._entries
                if e.kind is not ProvenanceKind.DEFAULT_ASSUMPTION]
        led = ProvenanceLedger()
        for e in kept:
            led.record(e.field_path, e.kind, e.detail)
        return led


def asserts_explicit_falsely(prov: Provenance, is_actually_inferred: bool) -> bool:
    """True iff ``prov`` claims authoritative (explicit/deterministic) origin for a
    value that is actually inferred. Used by the critical-failure detector."""
    return is_actually_inferred and prov.kind in AUTHORITATIVE_PROVENANCE


@dataclass(frozen=True)
class PrecedenceOutcome:
    winner: Provenance
    loser: Provenance
    winner_kind: ProvenanceKind
    reason: str


def resolve_precedence(a: Provenance, b: Provenance) -> PrecedenceOutcome:
    """Deterministically choose the higher-precedence provenance. Ties (same kind)
    resolve to ``a`` (stable, order-preserving)."""
    ra, rb = precedence_rank(a.kind), precedence_rank(b.kind)
    if ra <= rb:
        return PrecedenceOutcome(a, b, a.kind,
                                 f"{a.kind.value} outranks {b.kind.value}"
                                 if ra < rb else f"tie, kept first ({a.kind.value})")
    return PrecedenceOutcome(b, a, b.kind,
                             f"{b.kind.value} outranks {a.kind.value}")


def is_authoritative_over(higher: ProvenanceKind, lower: ProvenanceKind) -> bool:
    """Precedence predicate used by the conflict resolver."""
    return precedence_rank(higher) < precedence_rank(lower)
