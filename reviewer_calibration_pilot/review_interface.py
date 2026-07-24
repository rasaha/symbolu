"""Phase 7 - Blinded review interface.

Two-stage apparatus a REAL reviewer drives:
  Stage A (blinded): artifact + context + evidence + source metadata, NO system result, NO other
                     reviewer's result -> reviewer submits an initial independent judgment.
  Stage B (post-reveal): the frozen system result (obligation, rationale, modifiers, invariants,
                     EvidenceAssurance/AssertionGate/ActionGate outcomes) -> reviewer submits a
                     post-reveal judgment, agreement, override, reason, confidence.

No reviewer action triggers enforcement or any external effect. Records are immutable once submitted.
Deterministic container logic; the human judgments come from real reviewers (absent here).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

INTERFACE_VERSION = "review_interface_v1"
_BLINDED_FIELDS = ("artifact_id", "text", "source_path", "source_kind", "claim_family", "risk_tier",
                   "source_role", "claim_actionability", "temporal_sensitivity")


@dataclass
class ReviewerJudgment:
    """A single reviewer's judgment at one stage."""
    obligation: str = ""
    risk_tier: str = ""
    source_authority: str = ""
    evidence_satisfies: Optional[bool] = None
    allow_would_be_safe: Optional[bool] = None
    qualification_needed: Optional[bool] = None
    review_required: Optional[bool] = None
    action_present: Optional[bool] = None
    acceptable_actiongate_outcome: str = ""
    confidence: float = 0.0
    review_time_seconds: float = 0.0


@dataclass
class ReviewRecord:
    artifact_id: str
    reviewer_id: str                          # pseudonymous
    stage_a: Optional[ReviewerJudgment] = None      # blinded
    stage_b: Optional[ReviewerJudgment] = None      # post-reveal
    system_revealed: bool = False
    agreement: Optional[bool] = None
    override: Optional[bool] = None
    override_direction: str = ""              # stricter | more_permissive | none
    override_reason: str = ""
    explanation_usefulness: Optional[int] = None    # 1-5
    trace_comprehensible: Optional[bool] = None
    missing_context: Optional[bool] = None
    enforced: bool = False                    # ALWAYS False
    interface_version: str = INTERFACE_VERSION
    _locked: bool = field(default=False, repr=False)


class BlindedReviewSession:
    """Drives one reviewer through one artifact. A reviewer NEVER sees the system result before
    submitting Stage A, and never sees another reviewer's result."""

    def __init__(self, reviewer_id: str, artifact: Dict[str, Any]):
        self.reviewer_id = reviewer_id
        self._artifact = artifact
        self.record = ReviewRecord(artifact_id=artifact["artifact_id"], reviewer_id=reviewer_id)

    def blinded_view(self) -> Dict[str, Any]:
        """Stage A view: no system result, no other reviewer result."""
        return {k: self._artifact.get(k) for k in _BLINDED_FIELDS if k in self._artifact}

    def submit_stage_a(self, judgment: ReviewerJudgment) -> None:
        if self.record.stage_a is not None:
            raise ValueError("stage A already submitted (immutable)")
        if self.record.system_revealed:
            raise ValueError("cannot submit blinded judgment after reveal")
        self.record.stage_a = judgment

    def reveal(self, system_result: Dict[str, Any]) -> Dict[str, Any]:
        """Stage B view: reveal the frozen system result ONLY after Stage A is submitted."""
        if self.record.stage_a is None:
            raise ValueError("must submit Stage A before reveal (blinding invariant)")
        self.record.system_revealed = True
        self._system = system_result
        return dict(system_result)

    def submit_stage_b(self, judgment: ReviewerJudgment, *, agreement: bool, override: bool,
                       override_direction: str = "none", override_reason: str = "",
                       explanation_usefulness: int = 3, trace_comprehensible: bool = True,
                       missing_context: bool = False) -> ReviewRecord:
        if not self.record.system_revealed:
            raise ValueError("must reveal before Stage B")
        if self.record.stage_b is not None:
            raise ValueError("stage B already submitted (immutable)")
        if override and not override_reason:
            raise ValueError("override requires a reason")
        r = self.record
        r.stage_b = judgment
        r.agreement = agreement
        r.override = override
        r.override_direction = override_direction if override else "none"
        r.override_reason = override_reason
        r.explanation_usefulness = explanation_usefulness
        r.trace_comprehensible = trace_comprehensible
        r.missing_context = missing_context
        r.enforced = False                    # invariant: no enforcement
        r._locked = True                      # immutable after Stage B
        return r
