"""
Deterministic pre-judge validation (DETERMINISTIC_VALIDATION.md).

These checks run BEFORE any judge. They are pure functions of the claim + the
document set — no randomness, no LLM. A claim that fails a hard deterministic check
is resolved here and never reaches the (more expensive) semantic judges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation.model import (
    ClaimStatus, Document, RelationshipClaim,
)

# Relationship types the layer recognizes as legal (schema/legality gate).
LEGAL_RELATIONSHIP_TYPES = frozenset({
    "SUPERSEDES", "EXEMPTS", "REQUIRES", "RESTRICTS", "REFERENCES",
    "AMENDS", "PRECEDES", "DELEGATES_TO",
})


@dataclass(frozen=True)
class DeterministicResult:
    passed: bool                      # True => proceed to judges
    # If not passed, a terminal status is assigned here.
    terminal_status: ClaimStatus | None
    reason: str
    checks: Mapping[str, bool]        # per-check pass/fail


def _entities_present(claim: RelationshipClaim) -> bool:
    return bool(claim.source_node) and bool(claim.target_node) \
        and claim.source_node != claim.target_node


def run_deterministic(
    claim: RelationshipClaim,
    documents: Mapping[str, Document],
    already_seen: Tuple[Tuple[str, str, str], ...] = (),
) -> DeterministicResult:
    """Legality, schema, duplicate, direction, document existence, citation validity.

    Returns a terminal status only for HARD failures:
      - illegal relationship type / malformed schema -> UNSUPPORTED (remove)
      - cited document missing / cited span missing   -> INSUFFICIENT_EVIDENCE (abstain)
      - exact duplicate of an already-retained claim  -> UNSUPPORTED (remove)
    Direction is checked structurally (source != target); a self-loop is malformed.
    """
    checks: Dict[str, bool] = {}

    # legality / schema
    legal = claim.relationship_type in LEGAL_RELATIONSHIP_TYPES
    checks["legality"] = legal
    schema_ok = _entities_present(claim) and bool(claim.relationship_id)
    checks["schema"] = schema_ok
    checks["direction_wellformed"] = claim.source_node != claim.target_node

    if not legal or not schema_ok:
        return DeterministicResult(
            False, ClaimStatus.UNSUPPORTED,
            "illegal relationship type or malformed schema", checks)

    # duplicate detection (same source/type/target already retained upstream)
    key = (claim.source_node, claim.relationship_type, claim.target_node)
    dup = key in set(already_seen)
    checks["duplicate"] = not dup
    if dup:
        return DeterministicResult(
            False, ClaimStatus.UNSUPPORTED, "exact duplicate claim", checks)

    # document existence
    docs_exist = all(d in documents for d in claim.cited_document_ids)
    checks["document_existence"] = docs_exist

    # citation validity (each cited span exists in a cited document)
    citation_ok = docs_exist
    if docs_exist:
        for sid in claim.cited_span_ids:
            found = any(documents[d].span(sid) is not None
                        for d in claim.cited_document_ids)
            if not found:
                citation_ok = False
                break
    checks["citation_validity"] = citation_ok

    if not docs_exist or not citation_ok:
        return DeterministicResult(
            False, ClaimStatus.INSUFFICIENT_EVIDENCE,
            "cited document or span does not exist", checks)

    # No cited evidence at all -> cannot ground the claim.
    if not claim.cited_span_ids:
        checks["has_citation"] = False
        return DeterministicResult(
            False, ClaimStatus.INSUFFICIENT_EVIDENCE,
            "claim cites no evidence spans", checks)
    checks["has_citation"] = True

    return DeterministicResult(True, None, "passed deterministic checks", checks)
