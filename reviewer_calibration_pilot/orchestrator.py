"""Phase 9 - Internal pilot orchestrator.

Wraps the existing machinery read-only and adds ONLY: reviewer linkage, blinded-review state, reviewer
timing, adjudication linkage, reviewer confidence, and pilot stop-condition state. It does NOT duplicate
frozen governance logic - it composes review_interface + policy_runner.

A real reviewer supplies the Stage-A and Stage-B judgments (a callback). In the absence of real
reviewers, the orchestrator is exercised only by a clearly-labelled MOCK reviewer in the dry run - never
as validation. Deterministic; no enforcement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from reviewer_calibration_pilot import review_interface as ri
from reviewer_calibration_pilot import policy_runner as pr

ORCHESTRATOR_VERSION = "reviewer_calibration_orchestrator_v1"


@dataclass
class LinkedReview:
    artifact_id: str
    reviewer_id: str
    system_result: Dict[str, Any]
    record: ri.ReviewRecord
    is_mock: bool = False                     # True marks a machinery-test reviewer (NEVER validation)


def process_artifact(artifact: Dict[str, Any], reviewer_id: str,
                     stage_a_fn: Callable[[Dict[str, Any]], ri.ReviewerJudgment],
                     stage_b_fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
                     *, is_mock: bool = False) -> LinkedReview:
    """Drive one (artifact, reviewer) pair: blinded judgment -> frozen policy run -> reveal -> post-reveal
    judgment. `stage_a_fn` receives the blinded view; `stage_b_fn` receives (blinded view, system reveal
    view) and returns a dict of post-reveal fields. Nothing enforces."""
    session = ri.BlindedReviewSession(reviewer_id, artifact)

    # Stage A - blinded (reviewer sees no system result)
    blinded = session.blinded_view()
    session.submit_stage_a(stage_a_fn(blinded))

    # frozen policy runs read-only AFTER the blinded judgment
    result = pr.run(artifact)

    # Stage B - reveal + post-reveal judgment
    reveal = session.reveal(pr.reveal_view(result))
    b = stage_b_fn(blinded, reveal)
    record = session.submit_stage_b(
        b["judgment"], agreement=b["agreement"], override=b["override"],
        override_direction=b.get("override_direction", "none"), override_reason=b.get("override_reason", ""),
        explanation_usefulness=b.get("explanation_usefulness", 3),
        trace_comprehensible=b.get("trace_comprehensible", True),
        missing_context=b.get("missing_context", False))

    return LinkedReview(artifact_id=artifact["artifact_id"], reviewer_id=reviewer_id,
                        system_result=pr.reveal_view(result), record=record, is_mock=is_mock)


@dataclass
class PilotState:
    """Live pilot state the orchestrator tracks (stop conditions evaluated in stop_conditions.py)."""
    processed: int = 0
    reviews: List[LinkedReview] = field(default_factory=list)
    stopped: bool = False
    stop_reason: str = ""
    enforced_any: bool = False                # ALWAYS False
    orchestrator_version: str = ORCHESTRATOR_VERSION

    def add(self, lr: LinkedReview) -> None:
        self.reviews.append(lr)
        self.processed += 1
