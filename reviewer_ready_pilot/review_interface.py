"""Phase 11 - Blinded two-stage review interface.

The apparatus a REAL reviewer drives. Blinding and immutability are enforced by construction:

  Stage A (blinded): the reviewer sees the artifact + surface metadata ONLY - never the system result,
                     never another reviewer's label. They submit an independent StageALabel.
  reveal:            the frozen system result is shown ONLY after Stage A is locked. Calling reveal (or
                     asking for the system result) before Stage A raises - the blinding invariant.
  Stage B (post-reveal): the reviewer submits a StageBLabel (agreement / override + reason / ActionGate
                     acceptability / usefulness). Override requires a reason and a direction.

Invariants:
  * enforced is ALWAYS False - no reviewer action triggers enforcement or any external effect.
  * records are immutable once each stage is submitted (no re-submission, no post-hoc edit).
  * the native ActionGate outcome is carried verbatim in the revealed result and never collapsed.

Labels are validated against schema.py; invalid labels are rejected, never repaired. The human judgments
come from real reviewers - none exist in this track. Deterministic container logic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot import schema

INTERFACE_VERSION = "review_interface_v1"
_BLINDED_FIELDS = ("artifact_id", "text", "source_path", "source_kind", "claim_family", "risk_tier",
                   "source_role", "claim_actionability", "temporal_sensitivity")
# fields that would reveal the system's answer - forbidden in the blinded view.
_FORBIDDEN_IN_BLIND = ("gold_obligation", "gold_explanation", "invariants_triggered", "final_obligation",
                       "rationale", "modifiers_applied", "reason_codes", "trap_type", "edge_type")


@dataclass
class ReviewRecord:
    artifact_id: str
    reviewer_id: str                                 # pseudonymous
    stage_a: Optional[schema.StageALabel] = None     # blinded
    stage_b: Optional[schema.StageBLabel] = None     # post-reveal
    system_revealed: bool = False
    system_result: Optional[Dict[str, Any]] = None   # populated only at reveal
    enforced: bool = False                           # ALWAYS False
    is_mock: bool = False                            # True only for simulated-workflow test data
    interface_version: str = INTERFACE_VERSION
    _locked: bool = field(default=False, repr=False)

    def as_dict(self) -> Dict[str, Any]:
        return {"artifact_id": self.artifact_id, "reviewer_id": self.reviewer_id,
                "stage_a": schema.stage_a_dict(self.stage_a) if self.stage_a else None,
                "stage_b": schema.stage_b_dict(self.stage_b) if self.stage_b else None,
                "system_revealed": self.system_revealed, "system_result": self.system_result,
                "enforced": self.enforced, "is_mock": self.is_mock,
                "interface_version": self.interface_version}


class BlindedReviewSession:
    """Drives one reviewer through one artifact. Blinding + immutability enforced by construction."""

    def __init__(self, reviewer_id: str, artifact: Dict[str, Any], *, is_mock: bool = False):
        self.reviewer_id = reviewer_id
        self._artifact = artifact
        self._system: Optional[Dict[str, Any]] = None
        self.record = ReviewRecord(artifact_id=artifact["artifact_id"], reviewer_id=reviewer_id,
                                   is_mock=is_mock)

    def blinded_view(self) -> Dict[str, Any]:
        """Stage A view: surface metadata only. Guaranteed free of any system-result field."""
        view = {k: self._artifact.get(k) for k in _BLINDED_FIELDS if k in self._artifact}
        assert not any(k in view for k in _FORBIDDEN_IN_BLIND), "blinded view must not reveal the answer"
        return view

    def submit_stage_a(self, label: schema.StageALabel) -> None:
        if self.record.stage_a is not None:
            raise ValueError("stage A already submitted (immutable)")
        if self.record.system_revealed:
            raise ValueError("cannot submit blinded judgment after reveal")
        errs = schema.validate_stage_a(label)
        if errs:
            raise ValueError(f"invalid Stage A label: {errs}")
        self.record.stage_a = label

    def system_result_available(self) -> bool:
        return self.record.system_revealed

    def reveal(self, system_result: Dict[str, Any]) -> Dict[str, Any]:
        """Reveal the frozen system result - ONLY after Stage A is locked (blinding invariant)."""
        if self.record.stage_a is None:
            raise ValueError("must submit Stage A before reveal (blinding invariant)")
        if self.record.system_revealed:
            return dict(self._system)  # idempotent
        self.record.system_revealed = True
        self._system = dict(system_result)
        self.record.system_result = dict(system_result)
        return dict(system_result)

    def submit_stage_b(self, label: schema.StageBLabel) -> ReviewRecord:
        if not self.record.system_revealed:
            raise ValueError("must reveal before Stage B")
        if self.record.stage_b is not None:
            raise ValueError("stage B already submitted (immutable)")
        errs = schema.validate_stage_b(label)
        if errs:
            raise ValueError(f"invalid Stage B label: {errs}")
        self.record.stage_b = label
        self.record.enforced = False          # invariant: never enforce
        self.record._locked = True            # immutable after Stage B
        return self.record
