"""Build reproducible routing evidence, decision traces, and the decision id.

The evidence is sufficient to reproduce candidate filtering and ranking: it fingerprints
the registry, request, and policy, and records every rejection (with its failing
constraints) and every eligible candidate's score. The decision id is a pure function of
those fingerprints, so identical inputs always yield the same id (no clock, no randomness).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

from .contracts import (
    CandidateScore,
    RoutingDecisionTrace,
    RoutingEvidence,
    SteeringRequest,
)
from .policy import RoutingPolicy
from .registry import CandidateRegistry


def request_fingerprint(request: SteeringRequest) -> str:
    payload = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"))
    return "req-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def decision_id(reg_fp: str, req_fp: str, pol_fp: str, ranked_ids: Tuple[str, ...]) -> str:
    payload = json.dumps(
        {"registry": reg_fp, "request": req_fp, "policy": pol_fp, "ranked": list(ranked_ids)},
        sort_keys=True, separators=(",", ":"))
    return "dec-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_evidence(
    registry: CandidateRegistry,
    request: SteeringRequest,
    policy: RoutingPolicy,
    considered: int,
    rejected: List[Dict[str, Any]],
    scores: List[CandidateScore],
) -> RoutingEvidence:
    return RoutingEvidence(
        registry_fingerprint=registry.fingerprint(),
        request_fingerprint=request_fingerprint(request),
        policy_fingerprint=policy.fingerprint(),
        candidates_considered=considered,
        eligible_count=len(scores),
        rejected=tuple(rejected),
        scores=tuple(s.to_dict() for s in scores),
    )


def build_trace(eligible_order: Tuple[str, ...], rejected_order: Tuple[str, ...],
                had_recommendation: bool) -> RoutingDecisionTrace:
    stages = (
        "discover_candidates",
        "apply_hard_constraints",
        "collect_eligible",
        "score_eligible" if had_recommendation else "no_eligible_candidate",
        "rank_and_tie_break" if had_recommendation else "emit_typed_no_candidate",
        "build_recommendation" if had_recommendation else "build_evidence_only",
    )
    return RoutingDecisionTrace(
        stages=stages,
        eligible_order=eligible_order,
        rejected_order=rejected_order,
    )


__all__ = ["request_fingerprint", "decision_id", "build_evidence", "build_trace"]
