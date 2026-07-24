"""Phase 12 - Reviewer assignment.

Deterministically assigns final-set artifacts to reviewers so that:
  * each artifact is reviewed independently by REVIEWERS_PER_ARTIFACT reviewers (for later agreement),
  * a reviewer is never assigned an artifact they declared a conflict of interest on,
  * assignment is role-aware (an artifact can require a role band; a reviewer must hold it),
  * load is balanced across eligible reviewers,
  * the mapping is reproducible (sorted, hash-free ordering) so audits can replay it.

No real reviewer roster exists in this track; `assign` takes a caller-supplied roster and produces the
plan the administrator would use. It NEVER invents reviewers. Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

REVIEWERS_PER_ARTIFACT = 2


@dataclass
class Reviewer:
    reviewer_id: str                      # pseudonymous, e.g. REV-A
    roles: Set[str] = field(default_factory=set)
    conflicts: Set[str] = field(default_factory=set)   # artifact_ids the reviewer must not see
    tenant: str = "internal"
    is_mock: bool = False


@dataclass
class Assignment:
    artifact_id: str
    reviewer_ids: List[str]
    required_role: Optional[str] = None


@dataclass
class AssignmentPlan:
    assignments: List[Assignment]
    unassigned: List[str]                 # artifacts that could not reach the reviewer quota
    per_reviewer_load: Dict[str, int]
    reviewers_per_artifact: int = REVIEWERS_PER_ARTIFACT

    def as_dict(self) -> Dict[str, Any]:
        return {"reviewers_per_artifact": self.reviewers_per_artifact,
                "assignments": [{"artifact_id": a.artifact_id, "reviewer_ids": a.reviewer_ids,
                                 "required_role": a.required_role} for a in self.assignments],
                "unassigned": self.unassigned, "per_reviewer_load": self.per_reviewer_load}


def _eligible(reviewer: Reviewer, artifact: Dict[str, Any], required_role: Optional[str],
              tenant: str) -> bool:
    if reviewer.tenant != tenant:
        return False
    if artifact["artifact_id"] in reviewer.conflicts:
        return False
    if required_role is not None and required_role not in reviewer.roles:
        return False
    return True


def assign(artifacts: List[Dict[str, Any]], roster: List[Reviewer], *,
           required_role_for: Optional[Dict[str, str]] = None, tenant: str = "internal",
           reviewers_per_artifact: int = REVIEWERS_PER_ARTIFACT) -> AssignmentPlan:
    """Produce a reproducible assignment plan. `required_role_for` optionally maps artifact_id -> role."""
    required_role_for = required_role_for or {}
    load: Dict[str, int] = {r.reviewer_id: 0 for r in roster}
    roster_sorted = sorted(roster, key=lambda r: r.reviewer_id)
    assignments: List[Assignment] = []
    unassigned: List[str] = []

    for art in sorted(artifacts, key=lambda a: a["artifact_id"]):
        aid = art["artifact_id"]
        role = required_role_for.get(aid)
        eligible = [r for r in roster_sorted if _eligible(r, art, role, tenant)]
        # least-loaded first, tie-break by id for determinism
        eligible.sort(key=lambda r: (load[r.reviewer_id], r.reviewer_id))
        chosen = eligible[:reviewers_per_artifact]
        for r in chosen:
            load[r.reviewer_id] += 1
        assignments.append(Assignment(artifact_id=aid, reviewer_ids=[r.reviewer_id for r in chosen],
                                      required_role=role))
        if len(chosen) < reviewers_per_artifact:
            unassigned.append(aid)

    return AssignmentPlan(assignments=assignments, unassigned=unassigned, per_reviewer_load=load,
                          reviewers_per_artifact=reviewers_per_artifact)
