"""
reasoning_router.py — explicit deterministic contract router (RM1 §8).

RM1 does NOT train a router. Routing is a fixed, auditable map from task contract to one of three
lanes. Every instance records its route and the reason.

    DETERMINISTIC_ONLY            thresholds, arithmetic, active-version selection, date validity,
                                  schema checks, authority membership, access checks, required-field
    DETERMINISTIC_PLUS_EVENT_ATTENTION
                                  support/opposition, material conflict, exception interaction,
                                  multi-record dependency, evidence-chain completion, relational
                                  ambiguity
    QUARANTINE_OR_REVIEW          missing required evidence, unresolved identity, materially
                                  ambiguous language, invalid provenance, unresolved authoritative
                                  conflict

The routing policy is an ARCHITECTURE RECOMMENDATION under test, not a previously validated result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..event_schema import EventRecord

DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
DETERMINISTIC_PLUS_EVENT_ATTENTION = "DETERMINISTIC_PLUS_EVENT_ATTENTION"
QUARANTINE_OR_REVIEW = "QUARANTINE_OR_REVIEW"

# task family → contract lane (frozen for RM1)
_DETERMINISTIC = {"exact_threshold", "active_policy", "active_vs_stale", "multi_record_chain",
                  "evidence_incomplete"}
_RELATIONAL = {"authoritative_source", "approval_req_vs_granted", "supporting_vs_opposing",
               "exception_interaction", "unresolved_conflict"}


@dataclass
class RouteDecision:
    route: str
    reason: str
    contract: str


def route(task_family: str, admitted: List[EventRecord], required_ids: List[int],
          eid_preservation: float) -> RouteDecision:
    admitted_ids = {r.evidence_id for r in admitted}
    # QUARANTINE lane: integrity failure or missing required evidence
    if eid_preservation < 1.0:
        return RouteDecision(QUARANTINE_OR_REVIEW, "evidence_id_preservation<1", task_family)
    if not admitted:
        return RouteDecision(QUARANTINE_OR_REVIEW, "no_admitted_evidence", task_family)
    # note: required_ids are the ORACLE ids and won't equal freshly-assigned ids; missingness is
    # judged by the deterministic reasoner's own abstention, so we only quarantine on integrity here.
    if task_family in _RELATIONAL:
        return RouteDecision(DETERMINISTIC_PLUS_EVENT_ATTENTION, "relational_contract", task_family)
    if task_family in _DETERMINISTIC:
        return RouteDecision(DETERMINISTIC_ONLY, "exact_or_lookup_contract", task_family)
    return RouteDecision(DETERMINISTIC_ONLY, "default_deterministic", task_family)
