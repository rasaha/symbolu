"""Phase 16 - Adjudication.

Resolves disagreements between reviewers on an artifact. An adjudicator (a separate role, Phase 2) reviews
the disagreeing blinded labels and records a resolution - OR records UNRESOLVED when the disagreement is a
genuine, irreducible domain judgment call. Forcing false consensus is prohibited; UNRESOLVED is a valid,
honest terminus.

Constraints (enforced):
  * The adjudicator must not have reviewed the artifact themselves (separation).
  * Adjudication consumes real reviewer records; mock records are excluded. With no real disagreement to
    resolve, the module returns NOT_EVALUATED - it never invents an adjudication.
  * Adjudication records the resolved obligation and a reason; it NEVER enforces or executes anything, and
    it does not tune the frozen policy.

Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot.qualification import short_level

RESOLVED = "RESOLVED"
UNRESOLVED = "UNRESOLVED"
NOT_EVALUATED = "NOT_EVALUATED"


@dataclass
class AdjudicationCase:
    artifact_id: str
    reviewer_ids: List[str]
    reviewer_obligations: List[str]
    disagreement_type: str


@dataclass
class AdjudicationResult:
    artifact_id: str
    outcome: str                          # RESOLVED | UNRESOLVED | NOT_EVALUATED
    resolved_obligation: Optional[str] = None
    adjudicator_id: Optional[str] = None
    reason: str = ""
    is_mock: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"artifact_id": self.artifact_id, "outcome": self.outcome,
                "resolved_obligation": self.resolved_obligation, "adjudicator_id": self.adjudicator_id,
                "reason": self.reason, "is_mock": self.is_mock}


def find_disputes(records: List[Dict[str, Any]]) -> List[AdjudicationCase]:
    """Find artifacts where real reviewers disagree on the Stage-A obligation level."""
    real = [r for r in records if not r.get("is_mock") and r.get("stage_a")]
    by_art: Dict[str, List[Dict[str, Any]]] = {}
    for r in real:
        by_art.setdefault(r["artifact_id"], []).append(r)
    cases: List[AdjudicationCase] = []
    for aid, recs in sorted(by_art.items()):
        levels = [short_level(r["stage_a"].get("obligation")) for r in recs]
        if len(set(levels)) > 1:
            cases.append(AdjudicationCase(artifact_id=aid,
                                          reviewer_ids=[r["reviewer_id"] for r in recs],
                                          reviewer_obligations=levels,
                                          disagreement_type="OBLIGATION_LEVEL"))
    return cases


def adjudicate(case: AdjudicationCase, *, adjudicator_id: str, resolution: Dict[str, Any],
               is_mock: bool = False) -> AdjudicationResult:
    """Record a real adjudicator's decision. `resolution` is supplied by a human adjudicator:
       {"unresolved": bool, "obligation": str, "reason": str}. This function NEVER decides for them."""
    if adjudicator_id in case.reviewer_ids:
        raise ValueError("adjudicator must not have reviewed the artifact (separation violated)")
    if resolution is None:
        raise ValueError("adjudication requires a human resolution; the module never fabricates one")

    if resolution.get("unresolved"):
        if not resolution.get("reason"):
            raise ValueError("UNRESOLVED requires a reason (irreducible ambiguity must be justified)")
        return AdjudicationResult(artifact_id=case.artifact_id, outcome=UNRESOLVED,
                                  adjudicator_id=adjudicator_id, reason=resolution["reason"],
                                  is_mock=is_mock)
    ob = resolution.get("obligation")
    if short_level(ob) is None:
        raise ValueError("a resolved adjudication must name an obligation level")
    if not resolution.get("reason"):
        raise ValueError("a resolved adjudication requires a reason")
    return AdjudicationResult(artifact_id=case.artifact_id, outcome=RESOLVED, resolved_obligation=ob,
                              adjudicator_id=adjudicator_id, reason=resolution["reason"], is_mock=is_mock)


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Overview of the adjudication workload from real records only."""
    disputes = find_disputes(records)
    if not disputes:
        real = [r for r in records if not r.get("is_mock") and r.get("stage_a")]
        return {"status": NOT_EVALUATED if not real else "NO_DISPUTES",
                "real_records": len(real), "disputes": 0,
                "note": "No real reviewer disagreements to adjudicate."}
    return {"status": "DISPUTES_PENDING_HUMAN_ADJUDICATION",
            "disputes": len(disputes),
            "artifacts": [c.artifact_id for c in disputes]}
