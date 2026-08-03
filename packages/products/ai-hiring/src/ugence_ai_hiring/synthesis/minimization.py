"""Data-minimization & protected-attribute policy for evidence synthesis (H2).

Encodes tenant-configurable controls so recommendation generation consumes a
bounded, minimized evidence package rather than the whole candidate record, and
so protected/prohibited attributes never enter the pipeline. This policy expresses
intent and enforces exclusion at the synthesis boundary; it does not by itself
guarantee external-data non-exposure (that depends on the configured adapter).
"""

from __future__ import annotations

from typing import Iterable

from ..domain.base import DomainModel

# Attribute keys that must never drive a hiring recommendation. Inference of these
# from names, photos, addresses, schools, language, medical, or family data is
# prohibited (see H2 §13).
DEFAULT_PROHIBITED_ATTRIBUTES = frozenset({
    "race", "ethnicity", "national_origin", "gender", "sex", "sexual_orientation",
    "age", "date_of_birth", "religion", "disability", "medical", "health",
    "pregnancy", "marital_status", "family", "children", "genetic",
    "photo", "photograph", "political_affiliation", "veteran_status",
})


class MinimizationPolicy(DomainModel):
    """Tenant-configurable minimization + protected-attribute controls."""

    max_items: int = 0                                   # 0 = unbounded
    excluded_fields: tuple[str, ...] = ()
    prohibited_attributes: tuple[str, ...] = tuple(sorted(DEFAULT_PROHIBITED_ATTRIBUTES))
    quarantined_hashes: tuple[str, ...] = ()
    allowed_evidence_types: tuple[str, ...] = ()         # empty = all types allowed
    policy_ref: str = "minimization/default"

    def prohibited_set(self) -> frozenset[str]:
        return frozenset(a.lower() for a in self.prohibited_attributes)

    def contains_prohibited(self, keys: Iterable[str]) -> tuple[str, ...]:
        """Return any supplied attribute keys that are prohibited."""
        banned = self.prohibited_set()
        hits = tuple(sorted({k for k in keys if k.lower() in banned}))
        return hits

    def is_quarantined(self, content_hash: str) -> bool:
        return content_hash in set(self.quarantined_hashes)

    def evidence_type_allowed(self, evidence_type: str) -> bool:
        return not self.allowed_evidence_types or evidence_type in self.allowed_evidence_types
