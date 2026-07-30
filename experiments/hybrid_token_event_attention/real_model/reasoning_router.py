"""
reasoning_router.py — explicit deterministic, contract-aware reasoning router (§8).

RM1 does NOT train a router. The route is a fixed function of the decision contract (task family)
and the admission state, and every routed decision records its route + reason for audit.

    DETERMINISTIC_ONLY               thresholds, arithmetic, active-version selection, date validity,
                                     schema checks, authority membership, access checks, exact
                                     required-field checks
    DETERMINISTIC_PLUS_EVENT_ATTENTION   support vs opposition, material conflict, exception
                                     interaction, multi-record dependency, evidence-chain completion,
                                     relational ambiguity
    QUARANTINE_OR_REVIEW             missing required evidence, unresolved identity, materially
                                     ambiguous language, invalid provenance, conflicting
                                     authoritative sources without a resolution rule

This routing policy is an architecture recommendation UNDER TEST — not a previously validated result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..event_schema import EventRecord

DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
DETERMINISTIC_PLUS_EVENT_ATTENTION = "DETERMINISTIC_PLUS_EVENT_ATTENTION"
QUARANTINE_OR_REVIEW = "QUARANTINE_OR_REVIEW"

# contract -> default route (before admission-based overrides)
DETERMINISTIC_FAMILIES = {
    "exact_threshold", "active_policy", "active_vs_stale", "multi_record_chain",
    "unresolved_conflict", "evidence_incomplete",
}
RELATIONAL_FAMILIES = {
    "approval_req_vs_granted", "authoritative_source", "supporting_vs_opposing",
    "exception_interaction",
}


@dataclass
class RouteDecision:
    route: str
    reason: str
    task_family: str
    n_admitted: int


def route(task_family: str, admitted: List[EventRecord], required_present: Optional[bool] = None,
          has_unresolved: bool = False, has_ambiguous: bool = False,
          has_invalid_provenance: bool = False) -> RouteDecision:
    """Decide the route for one instance. Admission-derived blockers dominate the contract default."""
    n = len(admitted)

    # 1. hard blockers -> quarantine / review
    if has_invalid_provenance:
        return RouteDecision(QUARANTINE_OR_REVIEW, "invalid_provenance", task_family, n)
    if has_unresolved:
        return RouteDecision(QUARANTINE_OR_REVIEW, "unresolved_identity", task_family, n)
    if has_ambiguous:
        return RouteDecision(QUARANTINE_OR_REVIEW, "materially_ambiguous", task_family, n)
    if required_present is False:
        return RouteDecision(QUARANTINE_OR_REVIEW, "missing_required_evidence", task_family, n)

    # 2. contract-default route
    if task_family in RELATIONAL_FAMILIES:
        return RouteDecision(DETERMINISTIC_PLUS_EVENT_ATTENTION, "relational_contract", task_family, n)
    if task_family in DETERMINISTIC_FAMILIES:
        return RouteDecision(DETERMINISTIC_ONLY, "exact_contract", task_family, n)
    # unknown contract: conservative deterministic-only
    return RouteDecision(DETERMINISTIC_ONLY, "unknown_contract_default", task_family, n)


def is_relational(task_family: str) -> bool:
    return task_family in RELATIONAL_FAMILIES
