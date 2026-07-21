"""
Deterministic relationship-conflict detection (Section 11).

A conflict is declared ONLY when two assertions have a comparable subject, a comparable
object, compatible/overlapping scope, an overlapping temporal range, and a *logically
incompatible* polarity, modality, or value. Merely differing predicates do not make a
conflict; a superseded/historical assertion is resolved by supersession, not a conflict.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    AssertionStatus, ConflictType, Modality, Polarity, RelationshipAssertion,
    RelationshipConflict, Temporality,
)

_PERMIT = {RelationshipType.PERMITTED_TO, RelationshipType.AUTHORIZED_BY}
_PROHIBIT = {RelationshipType.PROHIBITS, RelationshipType.PROHIBITED_FROM}
_PAST = {Temporality.HISTORICAL, Temporality.SUPERSEDED}


def _value(a: RelationshipAssertion) -> str:
    return a.scope.get("value", "")


def _scope_overlap(a: RelationshipAssertion, b: RelationshipAssertion) -> bool:
    ga, gb = a.scope.get("geography"), b.scope.get("geography")
    if ga and gb and ga != gb:
        return False
    return True


def _temporal_overlap(a: RelationshipAssertion, b: RelationshipAssertion) -> bool:
    return not (a.temporality in _PAST or b.temporality in _PAST)


def _comparable_object(a: RelationshipAssertion, b: RelationshipAssertion) -> bool:
    return a.normalized_object == b.normalized_object and bool(a.normalized_object)


def detect_conflicts(assertions: List[RelationshipAssertion]
                     ) -> Tuple[RelationshipConflict, ...]:
    out: List[RelationshipConflict] = []
    n = len(assertions)
    cid = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = assertions[i], assertions[j]
            if not _scope_overlap(a, b) or not _temporal_overlap(a, b):
                continue
            ctype = None
            same_triple = (a.normalized_subject == b.normalized_subject
                           and a.normalized_predicate == b.normalized_predicate
                           and a.normalized_object == b.normalized_object)

            # POLARITY: same relationship asserted positively and negatively
            if same_triple and {a.polarity, b.polarity} == {Polarity.POSITIVE, Polarity.NEGATED}:
                ctype = ConflictType.POLARITY_CONFLICT
            # MODALITY: must vs may on the same relationship
            elif same_triple and {a.modality, b.modality} == {Modality.REQUIRED, Modality.PERMITTED}:
                ctype = ConflictType.MODALITY_CONFLICT
            # VALUE: same subject+predicate, comparable object, different explicit value
            elif (a.normalized_subject == b.normalized_subject
                  and a.normalized_predicate == b.normalized_predicate
                  and _value(a) and _value(b) and _value(a) != _value(b)):
                ctype = ConflictType.VALUE_CONFLICT
            # ONTOLOGY: permit vs prohibit on the same object
            elif (_comparable_object(a, b)
                  and ((a.relationship_type in _PERMIT and b.relationship_type in _PROHIBIT)
                       or (a.relationship_type in _PROHIBIT and b.relationship_type in _PERMIT))):
                ctype = ConflictType.ONTOLOGY_CONFLICT

            if ctype is not None:
                cid += 1
                out.append(RelationshipConflict(
                    conflict_id=f"C{cid}", assertion_ids=(a.assertion_id, b.assertion_id),
                    conflict_type=ctype, scope_overlap=_scope_overlap(a, b),
                    temporal_overlap=_temporal_overlap(a, b), severity="high",
                    explanation=f"{a.assertion_id} vs {b.assertion_id}: {ctype.value}"))
    return tuple(out)
